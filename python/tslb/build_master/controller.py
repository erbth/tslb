"""
The core of the build master

How to store graphs? - It seems suitable to use dependency lists because they
allow for easy traversal and Tarjan's algorithm, which is important to the
scheduler, finally uses dependency lists, too.

A Python-native implementation should use dicts in the simplest case.
"""
import queue
import re
from bm_interface import BMInterface
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb import tarjan
from tslb.Console import Color
from tslb.build_master.package_interface import StubPackageInterface
from tslb.build_master.cluster_interface import MockClusterInterface


class Controller(BMInterface):
    STATE_OFF = 'off'
    STATE_IDLE = 'idle'
    STATE_COMPUTING = 'computing'

    def __init__(self, loop, identity):
        self._loop = loop
        self._identity = identity

        # Basic controlling FSM state
        self._internal_state = self.STATE_OFF
        self._arch = Architecture.amd64
        self._error = False
        self._valve = False

        # Data structures used by the build master algorithm
        self._G = None
        self._GT = None

        # A map SCC-number -> nodes
        self._SCCs = None

        # A map node -> SCC-number
        self._node_to_scc = None

        # The contracted transposed dependency graph with SCC-numbers
        # (therefore SCCs) as nodes.
        self._HT = None

        # A map package name -> version
        self._versions = None

        self._remaining_set = None
        self._build_queue = None
        self._building_set = None

        # A map build node -> is busy
        self._nodes = {}

        # Interfaces to the packages and the build cluster used while the build
        # is active
        self._package_interface = None
        self._cluster_interface = None

        # Subscribers and log handlers
        self._subscribers = []
        self._log_handlers = []


    def _build_dependency_graph(self):
        """
        Builds the dependency graph G based on the packages and populates
        versions.
        """
        self._G = {}
        self._versions = {}

        # Set nodes.
        for pkg, v in self._package_interface.get_packages():
            self._G[pkg] = []
            self._versions[pkg] = v

        # Add edges
        for pkg in self._G:
            cdeps = self._package_interface.get_cdeps((pkg, self._versions[pkg]))

            for cdep in cdeps.get_required():
                if cdep not in self._G:
                    raise GenericBMError("Package `%s' requires `%s' but the latter does not exist." %
                            (pkg, cdep))

                if (cdep, self._versions[cdep]) not in cdeps:
                    raise GenericBMError(
                            "Package `%s' requires `%s' but the version to build does not satisfy the constraints." %
                            (pkg, cdep))

                self._G[pkg].append(cdep)

        # Compute transposed graph
        self._GT = {v: [] for v in self._G}

        for v in self._G:
            for u in self._G:
                self._GT[u].append(v)


    def _find_scc(self):
        """
        Finds SCCs in the given dependency graph using Tarjan's algorithm.
        """
        self._node_to_scc, _ = tarjan.find_scc(self._G)
        self._SCC = {}

        for v, scc in self._node_to_scc.items():
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
                r = self._node_to_scc[v]
                s = self._node_to_scc[u]

                if r != s:
                    self._HT[r].add(s)


    def _start_build(self):
        """
        Start a build by allocating resources and computing data
        representations needed during the build. This is where most of the work
        happens.

        Note that this requires that the state is already set to computing.
        """
        self._log('\n' + '-' * 80 + "\n\nStarting ...\n")

        if self._internal_state != self.STATE_COMPUTING:
            raise ces.SavedYourLife("The internal state is `%s' and not `computing'." %
                    self._internal_state)

        # Instantiate interfaces to the packages and to the build cluster
        self._package_interface = StubPackageInterface(self._arch)
        self._cluster_interface = MockClusterInterface(self._loop, self._arch)

        # Build required graphs
        try:
            self._log("Building dependency graph G ...\n")
            self._build_dependency_graph()

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

        except GenericBMError as e:
            self._log(Color.RED + "Error: " + Color.NORMAL + str(e) + "\n")
            self._stop_build()
            return

        # Fill the remaining set and initialize the build queue along with the
        # building set.
        self._remaining_set = set(self._GT.keys())
        self._build_queue = queue.PriorityQueue()
        self._building_set = set()

        # Identify packages with which to begin the build (the build master
        # algorithm computes a topological sorting interactively)
        self._find_initial_packages()

        self._nodes = {'node1:0': False, 'node2:0': False}

        # Call the scheduler (It will also change the internal state to 'idle'
        # once it exists.)
        self._schedule()

        self._notify_subscribers(self.DOMAIN_ALL)


    def _find_initial_packages(self):
        for pkg, neighbors in self._G.items():
            if len(neighbors) == 0:
                self._add_to_build_queue(pkg)


    def _add_to_build_queue(self, pkg):
        """
        Add a package to the build queue with a priority indirectly
        proportional to its 'fan-out' that is the number of neighbors that may
        be ready to be built after this package is built.
        """
        self._build_queue.put((1 / len(self._GT[pkg]), pkg))


    def _stop_build(self):
        """
        Stop a currently running build. The caller must ensure that it is safe
        to do so. Whenever this function is called from a different place thant
        `_start_build`, this usually means checking that `_internal_state` is
        'idle'.
        """
        self._internal_state = self.STATE_OFF

        # Clear data structures
        self._error = False
        self._valve = False

        self._G = None
        self._GT = None
        self._SCC = None
        self._node_to_scc
        self._HT = None

        self._versions = None

        self._remaining_set = None
        self._build_queue = None
        self._bulding_set = None

        self._package_interface = None
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
            idle_nodes = []
            for node, busy in self._nodes.items():
                if not busy:
                    idle_nodes.append(node)

            while not self._build_queue.empty() and idle_nodes:
                _, pkg = self._build_queue.get()

                i = self._find_best_node(idle_nodes)

                node = idle_nodes[0]
                del idle_nodes[0]

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
        # number of nodes running on it.
        nodes_per_host = {}
        builds_per_host = {}

        for node, busy in self._nodes.items():
            m = re.match(r'^(.+):[^:]+$', node)
            if m:
                host = m.group(1)
            else:
                host = node

            if host not in nodes_per_host:
                nodes_per_host[host] = 0
                builds_per_host[host] = 0

            nodes_per_host[host] += 1

            if busy:
                builds_per_host[host] += 1

        # Find the best node
        best = None
        best_ratio = 2

        for i, node in enumerate(nodes):
            m = re.match(r'^(.+):[^:]+$', node)
            if m:
                host = m.group(1)
            else:
                host = node

            ratio = builds_per_host[host] / nodes_per_host[host]
            if ratio < best_ratio:
                best_ratio = ratio
                best = i

        if best:
            return best

        return -1


    def _bind(self, pkg, node):
        """
        Bind a package to a build node.
        """
        self._nodes[node] = True
        self._building_set.add(pkg)


    def _notify_subscribers(self, domain):
        for subs in self._subscribers:
            subs(self, domain)

    def _log(self, msg, flush=False):
        for h in self._log_handlers:
            h(msg, flush)


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

        for node, busy in self._nodes.items():
            if busy:
                busy_nodes.append(node)
            else:
                idle_nodes.append(node)

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

        self._loop.call_soon(self._start_build)

    def stop(self):
        if self._internal_state != self.STATE_IDLE:
            raise ces.InvalidState("The controller's state is not `idle'.")

        self._stop_build()

    def open(self):
        if self._internal_state == self.STATE_OFF:
            raise ces.InvalidState("No build was started.")

        if self._error:
            raise ces.InvalidState("An error condition is present.")

        if self._valve:
            raise ces.InvalidState("The package valve is already open.")

        self._valve = True
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
