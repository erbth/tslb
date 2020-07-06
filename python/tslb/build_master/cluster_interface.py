"""
An interface to the build cluster that is the build nodes.
"""
import asyncio
import json
import random
import threading
import yamb_node
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb.VersionNumber import VersionNumber
from tslb.build_node import TSLB_NODE_YAMB_PROTOCOL


def create_cluster_interface(loop, arch):
    """
    Single-function factory for creating mock or real cluster interfaces.

    :param loop: An asyncio event loop
    :param str/int arch: Architecture
    :returns: ClusterInterface
    """
    return MockClusterInterface(loop, arch)


# Abstract interface class
class ClusterInterface:
    """
    An abstract base class for the build cluster interface.

    :param loop: An asyncio event loop
    :param yamb_node: An yamb node to communicate in the cluster
    :param str/int arch: Architecture
    """
    def __init__(self, loop, yamb_node, arch):
        raise NotImplementedError

    def get_build_nodes(self):
        """
        Return a list of build nodes that is known at the very point in time
        when this method is called.

        :returns list(BuildNodeProxy):
        """
        raise NotImplementedError

    def subscribe(self, subscriber):
        """
        Subscribers are notified if new build nodes are discovered and if build
        nodes disappear.

        :param subscriber: A callable with signature (cluster_interface).
        """
        raise NotImplementedError

    def unsubscribe(self, subscriber):
        raise NotImplementedError


class BuildNodeProxy:
    """
    An abstract base class for the build node interface that is the proxy
    objects that are part of the build cluster interface and represent build
    nodes. They shall only be instantiated by the build cluster interface.
    """
    STATE_IDLE = 'idle'
    STATE_BUILDING = 'building'
    STATE_FAILED = 'failed'
    STATE_FINISHED = 'finished'
    STATE_MAINTENANCE = 'maintenance'
    STATE_BUSY = 'busy'

    FAIL_REASON_NODE_TRY_AGAIN = 'node/try_again'
    FAIL_REASON_NODE_ABORT = 'node/abort'
    FAIL_REASON_PACKAGE = 'package'

    def __init__(self):
        raise NotImplementedError

    @property
    def identity(self):
        """
        :returns str:
        """
        raise NotImplementedError

    def get_state(self):
        """
        The following states exist:
            ('idle',)
            ('building', pkg name, version)
            ('failed', pkg name, version, reason)
            ('finished', pkg name, version)
            ('maintenance',)
            ('busy',)

        :returns tuple(str, ...): (state, additional infos ...)
        """
        raise NotImplementedError

    def start_build(self, package):
        """
        Start to build a specific package. This method is asynchronous. Wait
        for status updates triggered by the cluster interface.

        :param tuple(str, VersionNumber) package:
        :returns: None
        """
        raise NotImplementedError

    def reset(self):
        """
        Reset a build node. This method is asynchronous. Wait for sttaus
        updates triggered by the cluster interface.

        :returns: None
        """
        raise NotImplementedError

    def subscribe(self, receiver):
        """
        Subscribe for status updates.

        :param receives: update receiver of the following signature:
            (node proxy handle)
        """
        raise NotImplementedError

    def unsubscribe(self, receiver):
        """
        Unsubscribe from status updates.

        :param receiver:
        """
        raise NotImplementedError


# Mock implementation
class MockClusterInterface(ClusterInterface):
    def __init__(self, loop, yamb_node, arch):
        self._loop = loop
        self._arch = Architecture.to_int(arch)
        self._nodes = [
            MockBuildNodeProxy(self, 'host1:0'),
            MockBuildNodeProxy(self, 'host1:1')
        ]

        self._subscribers = []

        # A second host with two more nodes will appear after two seconds.
        self._loop.call_later(2, self._add_host)

    def get_build_nodes(self):
        return list(self._nodes)

    def subscribe(self, subscriber):
        for subs in self._subscribers:
            if subs is subscriber:
                return

        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        for i, subs in enumerate(self._subscribers):
            if subs is subscriber:
                del self._subscribers[i]

    def _add_host(self):
        self._nodes += [
            MockBuildNodeProxy(self, 'host2:0'),
            MockBuildNodeProxy(self, 'host2:1')
        ]
        self._notify_subscribers()

    def _notify_subscribers(self):
        for subs in self._subscribers:
            subs(self)


class MockBuildNodeProxy(BuildNodeProxy):
    def __init__(self, ci, identity):
        self._mutex = threading.RLock()
        with self._mutex:
            self._ci = ci
            self._loop = ci._loop
            self._identity = identity
            self._state = 'idle'
            self._pkg_name = None
            self._pkg_version = None
            self._fail_reason = None
            self._subscribers = []

    @property
    def identity(self):
        with self._mutex:
            return self._identity

    def get_state(self):
        with self._mutex:
            if self._state == 'idle':
                return (self.STATE_IDLE,)

            elif self._state == 'building':
                return (self.STATE_BUILDING, self._pkg_name, self._pkg_version)

            elif self._state == 'failed':
                return (self.STATE_FAILED, self._pkg_name, self._pkg_version, self._fail_reason)

            elif self._state == 'finished':
                return (self.STATE_FINISHED, self._pkg_name, self._pkg_version)

            elif self._state == 'maintenance':
                return (self.STATE_MAINTENANCE,)

            elif self._state == 'busy':
                return (self.STATE_BUSY,)

            raise ces.SavedYourLife('Invalid internal state: %s' % self._state)

    def start_build(self, package):
        with self._mutex:
            pkg_name, pkg_version = package
            pkg_version = VersionNumber(pkg_version)

            if self._state != 'idle':
                raise ces.InvalidState(self._state)

            self._state = 'busy'
            self._pkg_name = pkg_name
            self._pkg_version = pkg_version

            self._notify_subscribers()

            def build():
                with self._mutex:
                    # if random.choice((True, False)):
                    if True:
                        self._state = 'finished'

                    else:
                        self._state = 'failed'
                        self._fail_reason = 'package'

                    self._notify_subscribers()

            def transit():
                with self._mutex:
                    self._state = 'building'
                    self._notify_subscribers()

                self._loop.call_soon_threadsafe(lambda: self._loop.call_later(3, build))

            self._loop.call_soon_threadsafe(lambda: self._loop.call_later(0.5, transit))

    def reset(self):
        with self._mutex:
            if self._state not in ('failed', 'finished', 'idle'):
                raise ces.InvalidState(self._state)

            self._state = 'busy'

            def transit():
                with self._mutex:
                    self._state = 'idle'
                    self._notify_subscribers()

            self._loop.call_soon_threadsafe(lambda: self._loop.call_later(0.5, transit))

    def subscribe(self, receiver):
        with self._mutex:
            for subs in self._subscribers:
                if subs is receiver:
                    return

            self._subscribers.append(receiver)

    def unsubscribe(self, receiver):
        with self._mutex:
            for i, subs in enumerate(self._subscribers):
                if subs is receiver:
                    del self._subscribers[i]
                    break


    def _notify_subscribers(self):
        for subscriber in self._subscribers:
            subscriber(self)


# Real implementation
class RealClusterInterface(ClusterInterface):
    def __init__(self, loop, yamb_node, arch):
        self._loop = loop
        self._arch = Architecture.to_int(arch)
        self._yamb = yamb_node

        self._build_nodes = {}
        self._search_timer = 1000

        self._yamb.register_protocol(TSLB_NODE_YAMB_PROTOCOL, self._node_protocol_handler)

        self._subscribers = []

        # Create timer task
        self._timer_task = self._loop.create_task(self._timer_1s())


    def __del__(self):
        self._yamb.register_protocol(TSLB_NODE_YAMB_PROTOCOL, None)
        self._timer_task.cancel()
        await self._timer_task


    async def _timer_1s(self):
        while True:
            await asyncio.sleep(1)
            self._search_for_nodes()


    def _send_message_to_node(self, dst, d):
        """
        Send a message to a build node

        :param int dst: Destination address
        :param dict d: JSON data to send
        """
        self._yamb.send_yamb_message(dst, TSLB_NODE_YAMB_PROTOCOL,
                json.dumps(d).encode('UTF-8'))


    def _search_for_nodes(self):
        """
        Send a build node discovery broadcast every 10 seconds.
        """
        self._search_timer += 1

        if self._search_timer >= 10:
            self._search_timer = 0

            self._send_message_to_node(yamb_node.ALL_NODES_ADDRESS, {
                'action': 'identify'
            })

        # Call the nodes' timers
        for node in self._build_nodes.values():
            node._timer_1s()

        # Remove nodes that seem dead
        removed = False

        for name in list(self._build_nodes.keys()):
            if self._build_nodes[name]._seems_dead:
                removed = True
                del self._build_nodes[name]

        if removed:
            self._notify_subscribers()


    def _node_protocol_handler(self, src, data):
        if src == self._yamb.get_own_address():
            return

        try:
            j = json.loads(data.decode('UTF-8'))
            identity = j.get('identity')

            # Ignore messages from other clients.
            if 'action' in j:
                return

            if not identity:
                print("Dropped an message from a build node with no identity")
                return
        
        except BaseException as e:
            print("Dropped a message from a build node: %s." % e)
            return

        node = self._build_nodes.get(identity)

        # If we don't know that build node already, we add it to our list.
        if node is None:
            node = RealBuildNodeProxy(self, identity)
            self._build_nodes[identity] = node
            node._message_received(src, j)
            self._notify_subscribers()

        # Otherwise we call that node's message handler.
        else:
            node._message_received(src, j)


    def get_build_nodes(self):
        return list(self._build_nodes.values())


    def subscribe(self, subscriber):
        for subs in self._subscribers:
            if subs is subscriber:
                return

        self._subscribers.append(subscriber)


    def unsubscribe(self, subscriber):
        for i, subs in enumerate(self._subscribers):
            if subs is subscriber:
                del self._subscribers[i]
                return


    def _notify_subscribers(self):
        for subs in self._subscribers:
            subs(self)


class RealBuildNodeProxy(BuildNodeProxy):
    def __init__(self, ci, identity):
        self._ci = ci
        self._arch = ci._arch
        self._identity = identity

        self._last_contact = 0

        # Time since the last status request was sent. A state request should
        # be sent every 10 seconds to tell the node that we are still alive.
        self._last_status_request = 0

        self._current_addr = None

        # The node's state
        self._state = self.STATE_BUSY
        self._pkg_name = None
        self._pkg_arch = None
        self._pkg_version = None
        self._fail_reason = None

        self._subscribers = []


    def _timer_1s(self):
        self._last_contact += 1
        self._last_status_request += 1

        if self._last_status_request > 10:
            self._send_status_request()


    def _send_message_to_node(self, d):
        """
        Send a message to the build node's last known address. The node's
        identity will be added automatically.

        :param dict d: The data to send as JSON format
        """
        d = dict(d)
        d['identity'] = self._identity

        self._ci._send_message_to_node(self._current_addr, d)


    def _send_status_request(self):
        self._last_status_request = 0
        self._send_message_to_node({'action': 'get_status'})


    @property
    def _seems_dead(self):
        return self._last_contact >= 30


    def _message_received(self, src, data):
        self._last_contact = 0

        # If the nodes address changed, request the node's state.
        if self._current_addr != src:
            self._current_addr = src
            self._send_status_request()

        new_state = data.get('state')
        new_pkg_name = data.get('name')
        new_pkg_arch = data.get('arch')
        new_pkg_version = data.get('version')
        new_fail_reason = data.get('reason')

        if new_pkg_arch is not None:
            try:
                new_pkg_arch = Architecture.to_int(new_pkg_arch)

            except:
                print("Dropped message due to invalid architecture.")
                return

        if new_pkg_version is not None:
            try:
                new_pkg_version = VersionNumber(new_pkg_version)

            except:
                print("Dropped message due to invalid version number.")
                return

        if \
                (new_state and new_state != self._state) or \
                (new_pkg_name and new_pkg_name != self._pkg_name) or \
                (new_pkg_arch is not None and new_pkg_arch != self._pkg_arch) or \
                (new_pkg_version is not None and new_pkg_version != self._pkg_version) or \
                (new_fail_reason is not None and new_fail_reason != self._fail_reason):

            if new_state == 'idle':
                self._state = self.STATE_IDLE

            elif new_state == 'building':
                if new_pkg_name is None or new_pkg_arch is None or new_pkg_version is None:
                    print("Dropped state change to building because of missing attribute.")
                    return

                self._state = self.STATE_BUILDING
                self._pkg_name = new_pkg_name
                self._pkg_arch = new_pkg_arch
                self._pkg_version = new_pkg_version

            elif new_state == 'finished':
                if new_pkg_name is None or new_pkg_arch is None or new_pkg_version is None:
                    print("Dropped state change to finished because of missing attribute.")
                    return

                self._state = self.STATE_FINISHED
                self._pkg_name = new_pkg_name
                self._pkg_arch = new_pkg_arch
                self._pkg_version = new_pkg_version

            elif new_state == 'failed':
                if new_pkg_name is None or new_pkg_arch is None or \
                        new_pkg_version is None or new_fail_reason is None:

                    print("Dropped state change to failed because of missing attribute.")
                    return

                self._state = self.STATE_FAILED
                self._pkg_name = new_pkg_name
                self._pkg_arch = new_pkg_arch
                self._pkg_version = new_pkg_version
                self._fail_reason = new_fail_reason

            elif new_state == 'maintenance':
                self._state = self.STATE_MAINTENANCE

            self._notify_subscribers()


    def _notify_subscribers(self):
        for subs in self._subscribers:
            subs(self)


    # The BuildNodeProxy interface
    @property
    def identity(self):
        return self._identity

    def get_state(self):
        if self._state in (self.STATE_IDLE, self.STATE_MAINTENANCE, self.STATE_BUSY):
            return (self._state,)

        elif self._state in (self.STATE_BUILDING, self.STATE_FINISHED):
            return (self._state, self._pkg_name, self._pkg_version)

        else:
            return (self._state, self._pkg_name, self._pkg_version, self._fail_reason)

    def start_build(self, package):
        pkg, version = package

        self._state = self.STATE_BUSY
        self._notify_subscribers()

        self._send_message_to_node({
            'action': 'start_build',
            'name': pkg,
            'arch': Architecture.to_str(self._arch),
            'version': str(version)
        })

    def reset(self):
        self._state = self.STATE_BUSY
        self._notify_subscribers()

        self._send_message_to_node({'action': 'reset'})

    def subscribe(self, subscriber):
        for subs in self._subscribers:
            if subs is subscriber:
                return

        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        for i, subs in enumerate(self._subscribers):
            if subs is subscriber:
                del self._subscribers[i]
                break
