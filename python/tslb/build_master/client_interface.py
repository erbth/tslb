"""
The yamb interface between build master and client
"""
import json
from tslb import Architecture


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


    # Process received messages
    def cmd_identify(self, dst):
        # Our own identity will be included automatically
        self.send_message_to_client(dst)


    def cmd_get_state(self, dst):
        state, arch, error, valve = self._controller.get_state()

        d = {
            'state': state,
            'arch': Architecture.to_str(arch),
            'error': error,
            'valve': valve
        }

        self.send_message_to_client(dst, d)


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
            pass

        elif cmd == 'get-build-queue':
            pass

        elif cmd == 'get-building-set':
            pass

        elif cmd == 'get-nodes':
            pass

        elif cmd == 'get-state':
            self.cmd_get_state(src)

        elif cmd == 'start':
            pass

        elif cmd == 'stop':
            pass

        elif cmd == 'open':
            pass

        elif cmd == 'close':
            pass

        elif cmd == 'subscribe':
            pass

        else:
            print("Dropped message with unknown cmd: `%s'." % cmd)
