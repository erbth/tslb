"""
The core of the build master

How to store graphs? - It seems suitable to use dependency lists because they
allow for easy traversal and Tarjan's algorithm, which is important to the
scheduler, finally uses dependency lists, too.

A Python-native implementation should use dicts in the simplest case.
"""
import asyncio
import queue
import re
from bm_interface import BMInterface
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb import tarjan
from tslb.Console import Color
from tslb.build_master.package_interface import StubPackageInterface, RealPackageInterface, InvalidConfiguration
from tslb.build_master.cluster_interface import MockClusterInterface, RealClusterInterface


class Controller(BMInterface):
    STATE_OFF = 'off'
    STATE_IDLE = 'idle'
    STATE_COMPUTING = 'computing'

    def __init__(self, loop, yamb_node, identity):
        self._loop = loop
        self._identity = identity
        self._yamb = yamb_node

        # Basic controlling FSM state
        self._internal_state = self.STATE_OFF
        self._arch = Architecture.amd64
        self._error = False
        self._valve = False

        # Cancellable asynchronous computing task
        self._computing_task = None

        # Data structures used by the build master algorithm
        self._G = None
        self._GT = None

        # A map SCC-number -> nodes
        self._SCCs = None

        # A map package -> SCC-number
        self._pkg_to_scc = None

        # The contracted transposed dependency graph with SCC-numbers
        # (therefore SCCs) as nodes.
        self._H = None
        self._HT = None

        # A map package name -> version
        self._versions = None

        self._remaining_set = None
        self._build_queue = None
        self._building_set = None
        self._finished_set = None

        # Track how often a package was built successfully, and how many
        # attempts failed.
        self._pkg_successful = None
        self._pkg_fails = None

        # A map of build nodes -> task assigned (None or a (package name,
        # version) tuple, or "reset" while the master waites for a node to
        # reset)
        self._nodes = {}

        # Interfaces to the packages and the build cluster used while the build
        # is active
        self._package_interface = None
        self._cluster_interface = None

        # Subscribers and log handlers
        self._subscribers = []
        self._log_handlers = []


    def __del__(self):
        # Stop asynchronous computing task
        if self._computing_task is not None:
            self._computing_task.cancel()

        # Unsubscribe from the build cluster
        if self._cluster_interface:
            self._cluster_interface.unsubscribe(self._cluster_notification)

        for node in self._nodes:
            node.unsubscribe(self._build_node_notification)


    async def _build_dependency_graph(self):
        """
        Builds the dependency graph G based on the packages and populates
        versions.

        :raises InvalidConfiguration:
        """
        self._G = {}
        self._versions = {}

        # Set nodes.
        for pkg, v in await self._package_interface.get_packages():
            self._G[pkg] = []
            self._versions[pkg] = v

        # Add edges
        for pkg in self._G:
            # 'yield' cpu for communication...
            await asyncio.sleep(0.0001)
            cdeps = self._package_interface.get_cdeps((pkg, self._versions[pkg]))

            for cdep in cdeps.get_required():
                if cdep not in self._G:
                    raise GenericBMError("Package `%s' requires `%s' but the latter does not exist.\n" %
                            (pkg, cdep))

                if (cdep, self._versions[cdep]) not in cdeps:
                    raise GenericBMError(
                            "Package `%s' requires `%s' but the version to build "
                            "does not satisfy the constraints.\n" %
                            (pkg, cdep))

                self._G[pkg].append(cdep)

        # Compute transposed graph
        self._GT = {v: [] for v in self._G}

        for v in self._G:
            for u in self._G[v]:
                self._GT[u].append(v)


    def _find_scc(self):
        """
        Finds SCCs in the given dependency graph using Tarjan's algorithm.
        """
        self._pkg_to_scc, _ = tarjan.find_scc(self._G)
        self._SCC = {}

        for v, scc in self._pkg_to_scc.items():
            if scc not in self._SCC:
                self._SCC[scc] = []

            self._SCC[scc].append(v)


    def _compute_contracted_transposed_dependency_graph(self):
        """
        Computes the contracted transposed dependency graph HT.
        """
        # SCCs as nodes
        self._HT = {v: set() for v in self._SCC}

        # The edges between nodes can be accumulated into edges between SCCs
        for v, neighbors in self._GT.items():
            for u in neighbors:
                r = self._pkg_to_scc[v]
                s = self._pkg_to_scc[u]

                if r != s:
                    self._HT[r].add(s)

        # Compute H
        self._H = {v: [] for v in self._HT}

        for v, neighbors in self._HT.items():
            for u in neighbors:
                self._H[u].append(v)


    async def _start_build(self):
        """
        Start a build by allocating resources and computing data
        representations needed during the build. This is where most of the work
        happens.

        Note that this requires that the state is already set to computing.
        """
        self._log('\n' + '-' * 80 + "\n\nStarting ...\n")

        if self._internal_state != self.STATE_COMPUTING:
            raise ces.SavedYourLife("The internal state is `%s' and not `computing'.\n" %
                    self._internal_state)

        # Instantiate an interface to the packages
        # self._package_interface = StubPackageInterface(self._arch)
        self._package_interface = RealPackageInterface(self._arch)

        # Build required graphs
        try:
            with self._package_interface.lock():
                self._log("Building dependency graph G ...\n")
                await self._build_dependency_graph()

                self._log("Findings SCCs ...\n")
                self._find_scc()

                self._log("  SCCs with more than one node:\n")
                sccs = []
                for scc, nodes in self._SCC.items():
                    if len(nodes) > 1:
                        sccs.append(scc)

                if sccs:
                    for scc in sccs:
                        self._log("    %d: %s\n" % (scc, self._SCC[scc]))
                else:
                    self._log("    None.\n")

                self._log("\nComputing the contracted transposed dependency graph HT ...\n")
                self._compute_contracted_transposed_dependency_graph()

        except (GenericBMError, InvalidConfiguration) as e:
            self._log(Color.RED + "Error: " + Color.NORMAL + str(e) + "\n")
            self._stop_build()
            return

        # Fill the remaining set and initialize the build queue along with the
        # building set.
        self._remaining_set = set(self._GT.keys())
        self._build_queue = queue.PriorityQueue()
        self._building_set = set()
        self._finished_set = set()

        self._pkg_successful = {pkg: 0 for pkg in self._GT.keys()}
        self._pkg_fails = {pkg: 0 for pkg in self._GT.keys()}

        # Identify packages with which to begin the build (the build master
        # algorithm computes a topological sorting interactively)
        self._find_initial_packages()

        # After the build master algorithm is ready to deal with nodes,
        # instantiate an interface to the build cluster.
        # self._cluster_interface = MockClusterInterface(self._loop, self._yamb, self._arch)
        self._cluster_interface = RealClusterInterface(self._loop, self._yamb, self._arch)

        # Call the scheduler (It will also change the internal state to 'idle'
        # once it exists.)
        self._schedule()

        # Subscribe and initially find build nodes
        self._cluster_interface.subscribe(self._cluster_notification)
        self._cluster_notification(self._cluster_interface)

        self._notify_subscribers(self.DOMAIN_ALL)


    def _find_initial_packages(self):
        """
        Find packages with which to start the build and add them to the build
        queue.
        """
        # Find SCCs with no incoming edges in HT. These are exactly the SCCs
        # with no outgoing edges in H.
        for scc, neighbors in self._H.items():
            if len(neighbors) == 0:
                # Find a package to start this SCC with
                pkg = self._scc_choose_package(scc)
                self._remaining_set.remove(pkg)
                self._add_to_build_queue(pkg)


    def _add_to_build_queue(self, pkg):
        """
        Add a package to the build queue with a priority indirectly
        proportional to its 'fan-out' that is the number of neighbors that may
        be ready to be built after this package is built.
        """
        priority = 1 / len(self._GT[pkg]) if len(self._GT[pkg]) > 0 else 2
        self._build_queue.put((priority, pkg))


    def _stop_build(self):
        """
        Stop a currently running build. The caller must ensure that it is safe
        to do so. Whenever this function is called from a different place than
        `_start_build`, this usually means checking that `_internal_state` is
        'idle'.
        """
        self._internal_state = self.STATE_OFF

        # Cancel potential ongoing computation
        if self._computing_task is not None:
            self._computing_task.cancel()
            self._computing_task = None

        # Unsubscribe from the build cluster
        if self._cluster_interface:
            self._cluster_interface.unsubscribe(self._cluster_notification)

        for node in self._nodes:
            node.unsubscribe(self._build_node_notification)

        # Clear data structures
        self._error = False
        self._valve = False

        self._G = None
        self._GT = None
        self._SCC = None
        self._pkg_to_scc = None
        self._H = None
        self._HT = None

        self._versions = None

        self._remaining_set = None
        self._build_queue = None
        self._bulding_set = None
        self._finished_set = None

        self._pkg_successful = None
        self._pkg_fails = None

        self._package_interface = None

        if self._cluster_interface:
            self._cluster_interface.close()
            self._cluster_interface = None

        self._nodes = {}

        self._notify_subscribers(self.DOMAIN_ALL)


    def _schedule(self):
        """
        If the package valve is open, take packages from the build queue and
        assign them to idle build nodes.
        """
        self._internal_state = self.STATE_COMPUTING
        # Does actually not work as desired as the whole build master is single
        # threaded and will block until the end of this function ...
        self._notify_subscribers(self.DOMAIN_STATE)

        if self._valve:
            idle_nodes = [node for node in self._nodes if self._node_is_available(node)]

            while not self._build_queue.empty() and idle_nodes:
                _, pkg = self._build_queue.get()

                i = self._find_best_node(idle_nodes)

                node = idle_nodes[i]
                del idle_nodes[i]

                self._bind(pkg, node)

        self._internal_state = self.STATE_IDLE
        self._notify_subscribers(self.DOMAIN_STATE)
        self._notify_subscribers(self.DOMAIN_BUILD_QUEUE)
        self._notify_subscribers(self.DOMAIN_BUILDING_SET)
        self._notify_subscribers(self.DOMAIN_NODES)


    def _find_best_node(self, nodes):
        """
        Find the best node to start a build among the nodes given.

        :param list nodes:
        :returns: an index into the given array of nodes or -1 if no node is
            available.
        """
        # Choose the node whose host has least active builds compared to the
        # number of nodes running on it. If multiple nodes have the same
        # relative number of running builds, choose the host with more nodes as
        # it is probably faster.
        nodes_per_host = {}
        builds_per_host = {}

        def get_host(node):
            m = re.match(r'^(.+):[^:]+$', node.identity)
            if m:
                return m.group(1)
            else:
                return node

        for node in self._nodes:
            host = get_host(node)

            if host not in nodes_per_host:
                nodes_per_host[host] = 0
                builds_per_host[host] = 0

            nodes_per_host[host] += 1

            if not self._node_is_available(node):
                builds_per_host[host] += 1

        # Find the best node
        best = None
        best_ratio = 2

        for i, node in enumerate(nodes):
            host = get_host(node)

            ratio = builds_per_host[host] / nodes_per_host[host]

            # Note that the second and-clause will only be executed if best
            # contains a valid number.
            if \
                    ratio < best_ratio or \
                    (ratio == best_ratio and nodes_per_host[host] > nodes_per_host[get_host(nodes[best])]):
                best_ratio = ratio
                best = i

        if best is not None:
            return best

        return -1


    def _bind(self, pkg, node):
        """
        Bind a package to a build node.
        """
        p = (pkg, self._versions[pkg])

        self._outdate_children(pkg)

        self._nodes[node] = p
        self._building_set.add(pkg)

        node.start_build(p)


    def _outdate_children(self, pkg):
        """
        Outdate a package's children.
        """
        outdate_stage = self._package_interface.compute_child_outdate(
                self._package_interface.get_next_stage(
                    (pkg, self._versions[pkg])))

        if not outdate_stage:
            return

        for c in self._GT[pkg]:
            # Case 1: The package is from a different SCC.
            if self._pkg_to_scc[pkg] != self._pkg_to_scc[c]:
                self._log(Color.CYAN + "Info:" + Color.NORMAL +
                        " Outdating `%s' stage `%s'.\n" % (c, outdate_stage))

                self._package_interface.outdate_package(
                        (c, self._versions[c]),
                        outdate_stage)

            # Case 2: The package is from the same SCC (implies that th SCC has
            # more than one package).
            else:
                # Only outdate the children which where not built two times
                # yet.
                if self._pkg_successful[c] < 2:
                    self._log(Color.CYAN + "Info:" + Color.NORMAL +
                            " Outdating `%s' stage `%s'.\n" % (c, outdate_stage))

                    self._package_interface.outdate_package(
                            (c, self._versions[c]),
                            outdate_stage)


    def _scc_choose_package(self, scc):
        """
        Given a SCC choose the next package to build.

        :returns str: A package name
        """
        # Invariant 1: There may not be packages with 0 successful builds and
        # with 2 successful builds in one SCC at the same time. More generally
        # the maximum distance between package levels (number of successful
        # build attempts) must not exceed 1.
        #
        # Invariant 2: This routine may only be called if the SCC is not failed
        # that is it must be possible to find a package to build.

        # Determine the minimum and maximum package level in the SCC
        min_level = min([self._pkg_successful[v] for v in self._SCC[scc]])
        max_level = max([self._pkg_successful[v] for v in self._SCC[scc]])

        # If they are equal, start a new phase
        if min_level == max_level:
            for v in self._SCC[scc]:
                if self._pkg_fails[v] == 0:
                    return v

        # Otherwise try to build the packages of the lower level that have not
        # been tried yet.
        else:
            for v in self._SCC[scc]:
                if self._pkg_successful[v] == min_level and self._pkg_fails[v] == 0:
                    return v

        raise ces.SavedYourLife("Looks like there are no packages that can be built.")


    def _scc_finished(self, scc):
        """
        Determines if an SCC is finished
        """
        return all([(v in self._finished_set) for v in self._SCC[scc]])


    def _scc_failed(self, scc):
        """
        Determines if an SCC failed
        """
        # The packages at the lowest level (having least successful builds)
        # determine if an SCC failed.
        lowest_level = min([self._pkg_successful[v] for v in self._SCC[scc]])

        for v in self._SCC[scc]:
            if self._pkg_successful[v] != lowest_level:
                continue

            if self._pkg_fails[v] == 0:
                return False

        return True


    def _handle_successful_build(self, pkg):
        """
        This method performs the package-side implications when a package was
        built successfully. Notificiation of subscribers is not required as
        `_schedule` is called later.
        """
        self._building_set.remove(pkg)
        self._pkg_successful[pkg] += 1

        # Reset the failed build counters of all packages in this SCC as
        # progress happened
        if len(self._SCC[self._pkg_to_scc[pkg]]) > 1:
            self._log(Color.CYAN + "Info:" + Color.NORMAL +
                    "Package `%s' in SCC %d succeeded, reseting all fail counters.\n" %
                    (pkg, self._pkg_to_scc[pkg]))

            self._log_scc_info(self._pkg_to_scc[pkg])

        for v in self._SCC[self._pkg_to_scc[pkg]]:
            self._pkg_fails[v] = 0

        if self._pkg_successful[pkg] == 2 or len(self._SCC[self._pkg_to_scc[pkg]]) == 1:
            self._finished_set.add(pkg)

        # Determine children that can be built now
        # Case 1: This SCC is finished.
        if self._scc_finished(self._pkg_to_scc[pkg]):
            # Continue with topological sorting SCCs
            for u in self._HT[self._pkg_to_scc[pkg]]:
                possible = True

                for w in self._H[u]:
                    if not self._scc_finished(w):
                        possible = False
                        break

                if possible:
                    pkg = self._scc_choose_package(u)
                    self._remaining_set.discard(pkg)
                    self._add_to_build_queue(pkg)

        # Case 2: More packages of this SCC must be built
        else:
            pkg = self._scc_choose_package(self._pkg_to_scc[pkg])
            self._remaining_set.discard(pkg)
            self._add_to_build_queue(pkg)


    def _handle_failed_build(self, pkg):
        """
        This method handles the package-side work when a package was built
        successfully. Notification of subscribers is not requires as
        `_schedule` is called later.

        :returns: False if the entire (controller) build should keep going,
            True if it should be failed.
        """
        self._building_set.remove(pkg)
        self._pkg_fails[pkg] += 1

        scc = self._pkg_to_scc[pkg]

        # If the hole SCC failed, fail the build.
        if self._scc_failed(scc):
            self._fail()
            self._log(Color.RED + "Error:" + Color.NORMAL +
                    " All packages in SCC `%d' failed.\n" % scc)

            self._log_scc_info(scc)

        # Otherwise try another package of this SCC.
        else:
            self._log(Color.CYAN + "Info:" + Color.NORMAL +
                    " Package `%s' in multi-package SCC %d failed, trying the next package.\n" %
                    (pkg, scc))

            self._log_scc_info(scc)

            pkg = self._scc_choose_package(scc)
            self._remaining_set.discard(pkg)
            self._add_to_build_queue(pkg)


    def _cluster_notification(self, cluster_interface):
        """
        New nodes were discovered or existing ones disappeared.
        """
        # Ignore notification if we are not idle. As all computing-phases are
        # blocking (apart from the initial graph computation during which we've
        # not subscribed to the build cluster yet), this should not lead to
        # missed events.
        if self._internal_state != self.STATE_IDLE:
            self._log(Color.ORANGE + "Warning:" + Color.NORMAL +
                    " Cluster notification while controller was not idle.\n")
            return

        existing_nodes = set(self._nodes.keys())
        retrieved_nodes = set(self._cluster_interface.get_build_nodes())

        # Determine new nodes
        new_nodes = retrieved_nodes - existing_nodes
        for node in new_nodes:
            self._nodes[node] = None
            node.subscribe(self._build_node_notification)

        # Determine lost nodes
        lost_nodes = existing_nodes - retrieved_nodes

        for node in lost_nodes:
            if self._nodes[node] != None:
                self._log(Color.RED + "Error:" + Color.NORMAL +
                        " Build node `%s' disappeared although it ran a build "
                        "for this build master.\n" % node.identity)

                self._fail()

            else:
                del self._nodes[node]

        if new_nodes:
            # We detected new nodes - maybe we can give them something to
            # build?
            self._schedule()


    def _build_node_notification(self, node):
        """
        A build node changed state.
        """
        t_state = node.get_state()
        state = t_state[0]

        # Hack: allow for changes to busy as that happens during _schedule.
        if self._internal_state != self.STATE_IDLE and state != node.STATE_BUSY:
            self._log(Color.ORANGE + "Warning:" + Color.NORMAL +
                    " Build node notification while controller was not idle.\n")
            return

        if state == node.STATE_BUSY:
            # Hack: nothing 'critical' maybe done here as this can happen
            # during _schedule
            pass

        elif state == node.STATE_IDLE:
            if isinstance(self._nodes[node], tuple):
                self._log(Color.RED + "Error:" + Color.NORMAL +
                        " Build node `%s' switched to state `idle' while it conducted a build.\n" %
                        node.identity)

                self._fail()

            else:
                self._nodes[node] = None

        elif state == node.STATE_BUILDING:
            if self._nodes[node] is None:
                pass

            elif self._nodes[node] == 'reset':
                self._log(Color.RED + "Error:" + Color.NORMAL +
                        " Build node `%s' switched to state building though it should have reset.\n" %
                        node.identity)

                self._fail()

            elif self._nodes[node] != (t_state[1:3]):
                self._log(Color.CYAN + "Info:" + Color.NORMAL +
                        " Build node `%s' started to build a different package than it was assigned.\n" %
                        node.identity)

                # Put the package back on the build queue
                self._building_set.discard(t_state[1])
                self._add_to_build_queue(t_state[1])
                self._nodes[node] = None

        elif state == node.STATE_FINISHED:
            if self._nodes[node] is not None:
                if t_state[1:3] == self._nodes[node]:
                    self._handle_successful_build(t_state[1])

                    # Reset the node after a successful build.
                    node.reset()
                    self._nodes[node] = 'reset'

                else:
                    self._log(Color.CYAN + "Info:" + Color.NORMAL +
                            " Build node `%s' finished to build a different package than it was assigned.\n" %
                            node.identity)

                    # Put the package back on the build queue
                    self._building_set.discard(t_state[1])
                    self._add_to_build_queue(t_state[1])
                    self._nodes[node] = None

        elif state == node.STATE_FAILED:
            if t_state[1:3] == self._nodes[node]:
                fail_reason = t_state[3]

                # If the error code was 'node/try_again', ignore the event and try
                # again.
                if fail_reason == node.FAIL_REASON_NODE_TRY_AGAIN:
                    self._log(Color.CYAN + "Info:" + Color.NORMAL +
                            " Build node `%s' failed with node/try_again, putting "
                            "the package back onto the build queue and not resetting the node.\n" %
                            node.identity)

                    # Put the package back on the build queue
                    self._building_set.discard(t_state[1])
                    self._add_to_build_queue(t_state[1])
                    self._nodes[node] = None

                # If the error code was 'node/abort', fail the build.
                elif fail_reason == node.FAIL_REASON_NODE_ABORT:
                    self._log(Color.RED + "Error:" + Color.NORMAL +
                            " Build node `%s' failed with node/abort, aborting the build.\n" %
                            node.identity)

                    self._building_set.remove(t_state[1])
                    self._fail()

                # If the error code was 'package', more elaborated logic must
                # be used.
                elif fail_reason == node.FAIL_REASON_PACKAGE:
                    if self._handle_failed_build(t_state[1]):
                        self._fail()

                    else:
                        node.reset()
                        self._nodes[node] = 'reset'

            elif self._nodes[node] is not None:
                # Ignore if something else than we requested failed.
                self._log(Color.CYAN + "Info:" + Color.NORMAL +
                        " Build node `%s' failed to build a different package than it was assigned.\n" %
                        node.identity)

                # Put the package back on the build queue
                self._building_set.discard(self._nodes[node])
                self._add_to_build_queue(self._nodes[node])
                self._nodes[node] = None

        elif state == node.STATE_MAINTENANCE:
            if self._nodes[node] is not None:
                self._log(Color.RED + "Error:" + Color.NORMAL +
                        " Build node `%s' switched to maintenance while it was "
                        "assigned a task or resetting.\n" %
                        node.identity)

                self._fail()

        else:
            raise ces.SavedYourLife("Received an unknown node state: `%s'." % state)

        # Maybe new nodes are packages became available. Additionally this will
        # notify clients.
        self._notify_subscribers(self.DOMAIN_REMAINING)

        # Hack: if state changed to busy, don't call schedule to avoid
        # reentrance
        if state != node.STATE_BUSY:
            self._schedule()


    def _fail(self):
        """
        Fail the current build.
        """
        self._error = True
        self._valve = False

        self._notify_subscribers(self.DOMAIN_STATE)


    def _node_is_available(self, node):
        """
        Determine if a node is available to build a package. This means that it
        has not task assigned yet and is idle.
        """
        return self._nodes[node] is None and node.get_state()[0] == node.STATE_IDLE


    def _log_scc_info(self, scc):
        self._log("SCC %d (successful / failed attempts):\n" % scc)
        for v in self._SCC[scc]:
            self._log("    `%s' (%d/%d)\n" % (v, self._pkg_successful[v], self._pkg_fails[v]))

        self._log("\n")

    def _notify_subscribers(self, domain):
        for subs in self._subscribers:
            subs(self, domain)

    def _log(self, msg, flush=False):
        for h in self._log_handlers:
            h(msg, flush=flush)


    # The BMInterface provided by this build master controller core
    # Log handlers
    @property
    def identity(self):
        return self._identity

    def get_remaining(self):
        if self._remaining_set is not None:
            return [(pkg, self._versions[pkg]) for pkg in self._remaining_set]
        else:
            return []

    def get_build_queue(self):
        if self._build_queue is not None:
            return [(e[1], self._versions[e[1]]) for e in self._build_queue.queue]
        else:
            return []

    def get_building_set(self):
        if self._building_set is not None:
            return [(pkg, self._versions[pkg]) for pkg in self._building_set]
        else:
            return []

    def get_nodes(self):
        idle_nodes = []
        busy_nodes = []

        for node in self._nodes:
            if self._node_is_available(node):
                idle_nodes.append(node.identity)
            else:
                busy_nodes.append(node.identity)

        return (idle_nodes, busy_nodes)

    def get_state(self):
        state = self._internal_state

        if self._building_set:
            state = 'building'

        return (state, Architecture.to_str(self._arch), self._error, self._valve)

    def start(self, arch):
        if self._internal_state != self.STATE_OFF:
            raise ces.InvalidState("The controller's state is not `off'.")

        self._arch = Architecture.to_str(arch)
        self._internal_state = self.STATE_COMPUTING

        self._notify_subscribers(self.DOMAIN_ALL)

        self._computing_task = self._loop.create_task(self._start_build())

    def stop(self):
        if self._internal_state not in (self.STATE_IDLE, self.STATE_COMPUTING):
            raise ces.InvalidState(
                    "The controller's state is not `idle' or `computing'.")

            if self._internal_state == self.STATE_COMPUTING and self._computing_task is None:
                raise ces.InvalidState(
                        "The controller's state is `computing' but the "
                        "computations are not cancellable.")

        self._stop_build()

    def open(self):
        if self._internal_state == self.STATE_OFF:
            raise ces.InvalidState("No build was started.")

        if self._error:
            raise ces.InvalidState("An error condition is present.")

        if self._valve:
            raise ces.InvalidState("The package valve is already open.")

        self._valve = True
        self._notify_subscribers(self.DOMAIN_STATE)

        # _schedule() if state is idle, otherwise the background computing task
        # will do this.
        if self._internal_state == self.STATE_IDLE:
            self._schedule()

    def close(self):
        if self._internal_state == self.STATE_OFF:
            raise ces.InvalidState("No build was started.")

        if not self._valve:
            raise ces.InvalidState("The package valve is already closed.")

        self._valve = False
        self._notify_subscribers(self.DOMAIN_STATE)

    def subscribe(self, subscriber):
        for subs in self._subscribers:
            if subs is subscriber:
                return

        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        for i, subs in enumerate(self._subscribers):
            if subs is subscriber:
                del self._subscribers[i]

    def register_log_handler(self, handler):
        for h in self._log_handlers:
            if handler is h:
                return

        self._log_handlers.append(handler)

    def deregister_log_handler(self, handler):
        for i,h in enumerate(self._log_handlers):
            if h is handler:
                del self._log_handlers[i]


#******************************* Exceptions ***********************************
class GenericBMError(Exception):
    pass
