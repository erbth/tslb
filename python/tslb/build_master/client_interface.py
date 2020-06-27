"""
The yamb interface between build master and client
"""
import json
from tslb import Architecture
from tslb import CommonExceptions as ces
from .bm_interface import BMInterface


# Constants
TSLB_MASTER_CLIENT_YAMB_PROTOCOL = 1001


class ClientInterface:
    """
    :param BMInterface controller:
    """
    def __init__(self, loop, yamb, controller):
        self._loop = loop
        self._yamb = yamb
        self._controller = controller

        self._yamb.register_protocol(TSLB_MASTER_CLIENT_YAMB_PROTOCOL, self.protocol_handler)

        # A list of nodes where state changes etc. should be sent to. It is a
        # map from yamb addresses into subscription time.
        self._subscribers = {}

        # Start timer
        self._loop.call_later(1, self._1s_timer)

        # Subscribe to controller
        self._controller.subscribe(self._notification_from_controller)

    def __del__(self):
        # Unsubscribe from controller
        self._controller.unsubscribe(self._notification_from_controller)


    def _1s_timer(self):
        """
        Called roughly once per second
        """
        to_remove = []
        for addr, time in self._subscribers.items():
            if time + 15 < self._loop.time():
                to_remove.append(addr)

        for addr in to_remove:
            del self._subscribers[addr]

        self._loop.call_later(1, self._1s_timer)


    def _notification_from_controller(self, controller, domain):
        if controller is not self._controller:
            raise ces.SavedYourLife(
                "Got a notification from a differen controller: `%r' is not `%r'." %
                (controller, self._controller))

        for dst in self._subscribers.keys():
            if domain == BMInterface.DOMAIN_STATE:
                self.cmd_get_state(dst)

            elif domain == BMInterface.DOMAIN_REMAINING:
                self.cmd_get_remaining(dst)

            elif domain == BMInterface.DOMAIN_BUILD_QUEUE:
                self.cmd_get_build_queue(dst)

            elif domain == BMInterface.DOMAIN_BUILDING_SET:
                self.cmd_get_building_set(dst)

            elif domain == BMInterface.DOMAIN_NODES:
                self.cmd_get_nodes(dst)

            elif domain == BMInterface.DOMAIN_ALL:
                self.cmd_get_remaining(dst)
                self.cmd_get_build_queue(dst)
                self.cmd_get_building_set(dst)
                self.cmd_get_nodes(dst)
                self.cmd_get_state(dst)

            else:
                raise ces.SavedYourLife("Invalid domain: %s" % domain)


    # Send a message to a client
    def send_message_to_client(self, dst, data={}):
        """
        Send a message to a client that includes our own identity along with
        the specified data.

        :param int dst: The client's address
        :param dict data: The data to send as kv-pairs.
        """
        d = dict(data)
        d['identity'] = self._controller.identity

        self._yamb.send_yamb_message(dst, TSLB_MASTER_CLIENT_YAMB_PROTOCOL,
                json.dumps(d).encode('utf8'))

    def send_error(self, dst, err):
        d = {
            'error': str(err)
        }
        self.send_message_to_client(dst, d)


    # Process received messages
    def cmd_identify(self, dst):
        # Our own identity will be included automatically
        self.send_message_to_client(dst)

    def cmd_get_remaining(self, dst):
        d = {
            'remaining': [(n, str(v)) for n,v in self._controller.get_remaining()]
        }
        self.send_message_to_client(dst, d)

    def cmd_get_build_queue(self, dst):
        d = {
            'build-queue': [(n, str(v)) for n,v in self._controller.get_build_queue()]
        } 
        self.send_message_to_client(dst, d)

    def cmd_get_building_set(self, dst):
        d = {
            'building-set': [(n, str(v)) for n,v in self._controller.get_building_set()]
        }
        self.send_message_to_client(dst, d)

    def cmd_get_nodes(self, dst):
        idle, busy = self._controller.get_nodes()
        d = {
            'idle-nodes': idle,
            'busy-nodes': busy
        }
        self.send_message_to_client(dst, d)

    def cmd_get_state(self, dst):
        state, arch, error, valve = self._controller.get_state()

        d = {
            'state': state,
            'arch': Architecture.to_str(arch),
            'error': error,
            'valve': valve
        }

        self.send_message_to_client(dst, d)

    def cmd_subscribe(self, dst):
        self._subscribers[dst] = self._loop.time()

    def cmd_start(self, dst, arch):
        try:
            self._controller.start(arch)
        except ces.InvalidState as e:
            self.send_error(dst, e)

    def cmd_stop(self, dst):
        try:
            self._controller.stop()
        except ces.InvalidState as e:
            self.send_error(dst, e)

    def cmd_open(self, dst):
        try:
            self._controller.open()
        except ces.InvalidState as e:
            self.send_error(dst, e)

    def cmd_close(self, dst):
        try:
            self._controller.close()
        except ces.InvalidState as e:
            self.send_error(dst, e)


    # Handle incoming messages
    def protocol_handler(self, src, data):
        """
        Handle incomming messages
        """
        if src == self._yamb.get_own_address():
            return

        try:
            j = json.loads(data.decode('utf8'))

            cmd = j.get('cmd')
            msg_identity = j.get('identity')

            if cmd != 'identify' and msg_identity != self._controller.identity:
                print("Dropped message for foreign identity")
                return

        except:
            print("Dropped message with unknown content")
            return

        if cmd == 'identify':
            self.cmd_identify(src)

        elif cmd == 'get-remaining':
            self.cmd_get_remaining(src)

        elif cmd == 'get-build-queue':
            self.cmd_get_build_queue(src)

        elif cmd == 'get-building-set':
            self.cmd_get_building_set(src)

        elif cmd == 'get-nodes':
            self.cmd_get_nodes(src)

        elif cmd == 'get-state':
            self.cmd_get_state(src)

        elif cmd == 'subscribe':
            self.cmd_subscribe(src)

        elif cmd == 'start':
            try:
                arch = Architecture.to_int(j.get('arch'))
            except (TypeError, KeyError):
                print("Ignored `start' message because it did not include a valid architecture.")
                return

            self.cmd_start(src, arch)

        elif cmd == 'stop':
            self.cmd_stop(src)

        elif cmd == 'open':
            self.cmd_open(src)

        elif cmd == 'close':
            self.cmd_close(src)

        else:
            print("Dropped message with unknown cmd: `%s'." % cmd)
