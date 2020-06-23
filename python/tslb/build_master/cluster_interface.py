"""
An interface to the build cluster that is the build nodes.
"""
import asyncio
import random
import threading
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb.VersionNumber import VersionNumber


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
    :param str/int arch: Architecture
    """
    def __init__(self, loop, arch):
        raise NotImplementedError

    def get_build_nodes(self):
        """
        Return a list of build nodes that is known at the very point in time
        when this method is called.

        :returns list(BuildNodeProxy):
        """
        raise NotImplementedError

class BuildNodeProxy:
    """
    An abstract base class for the build node interface that is the proxy
    objects that are part of the build cluster interface and represent build
    nodes. They shall only be instantiated by the build cluster interface.
    """
    def __init__(self):
        raise NotImplementedError

    @property
    def name(self):
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
            (node proxy handle, state: tuple(str, ...))
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
    def __init__(self, loop, arch):
        self._loop = loop
        self._arch = Architecture.to_int(arch)
        self._nodes = [
            MockBuildNodeProxy(self, 'node1'),
            MockBuildNodeProxy(self, 'node2'),
            MockBuildNodeProxy(self, 'node3')
        ]

    def get_build_nodes(self):
        return list(self._nodes)


class MockBuildNodeProxy(BuildNodeProxy):
    def __init__(self, ci, name):
        self._mutex = threading.RLock()
        with self._mutex:
            self._ci = ci
            self._loop = ci._loop
            self._name = name
            self._state = 'idle'
            self._pkg_name = None
            self._pkg_version = None
            self._fail_reason = None
            self._subscribers = []

    @property
    def name(self):
        with self._mutex:
            return self._name

    def get_state(self):
        with self._mutex:
            if self._state == 'idle':
                return ('idle',)

            elif self._state == 'building':
                return ('building', self._pkg_name, self._pkg_version)

            elif self._state == 'failed':
                return ('failed', self._pkg_name, self._pkg_version, self._fail_reason)

            elif self._state == 'finished':
                return ('finished', self._pkg_name, self._pkg_version)

            elif self._state == 'maintenance':
                return ('maintenance',)

            elif self._state == 'busy':
                return ('busy',)

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

            async def build():
                await asyncio.sleep(3)
                with self._mutex:
                    if random.choice((True, False)):
                        self._state = 'finished'

                    else:
                        self._state = 'failed'
                        self._fail_reason = 'package'

                    self._notify_subscribers()

            async def transit():
                await asyncio.sleep(0.5)
                with self._mutex:
                    self._state = 'building'
                    self._notify_subscribers()

                asyncio.run_coroutine_threadsafe(build(), self._loop)

            asyncio.run_coroutine_threadsafe(transit(), self._loop)

    def reset(self):
        with self._mutex:
            if self._state not in ('failed', 'finished', 'idle'):
                raise ces.InvalidState(self._state)

            self._state = 'busy'

            async def transit():
                await asyncio.sleep(0.5)
                with self._mutex:
                    self._state = 'idle'
                    self._notify_subscribers()

            asyncio.run_coroutine_threadsafe(transit(), self._loop)

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
        msg = None

        if self._state == 'idle':
            msg = ('idle',)

        elif self._state == 'building':
            msg = ('building', self._pkg_name, self._pkg_version)

        elif self._state == 'failed':
            msg = ('failed', self._pkg_name, self._pkg_version, self._fail_reason)

        elif self._state == 'finished':
            msg = ('finished', self._pkg_name, self._pkg_version)

        elif self._state == 'maintenance':
            msg = ('maintenance',)

        elif self._state == 'busy':
            msg = ('busy',)

        else:
            raise ces.SavedYourLife('Invalid internal state: %s' % self._state)

        for subscriber in self._subscribers:
            subscriber(self, msg)


# Real implementation
