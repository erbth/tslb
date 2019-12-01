import asyncio
import json
import logging
import socket
import yamb_node
from tslb.build_node import TSLB_NODE_YAMB_PROTOCOL
from tslb.build_master import TSLB_MASTER_CLIENT_YAMB_PROTOCOL
from tslb import timezone
from tslb.build_node import BuildNode
from tslb.Architecture import architectures, architectures_reverse
from tslb.VersionNumber import VersionNumber

# The Build Master <-> Build Node protocol:
# The protocol is composed of messages which are serialized jsons.
#
# Master -> Node messages:
# Each message has an action field. More fields may be added as needed. Unlike
# in the other direction, the master does currently only request the nodes to
# to things but does e.g. not broadcast state changes. The nodes have no use for
# such information.
#    * action=identify: Request the node to identify itself.
#
# Node -> Master messages:
# Each message has an identity field. Further fields may be added that tell the
# master about the nodes state or request it to do something.

# The Build Master <-> Client protocol:
# Same thing here, but a different protocol number and different messages.
#
# Client -> Master messages:
# Again, the action field is mandatory.
#   * action=identify: To find the master's yamb address and identity. The
#       latter is more or less unique.
#   * action=request-node-list
#   * action=request-node-states, nodes=<list(str): identities>
#   * action=start-build / stop-build
#   * action=request-build-state
#   * action=request-node-output, nodes=<list(str): identities>
#
# Master -> Client messages:
# The identity field is contained in every message.
#   * identity=str
#   * node-list=list(str: node identitiy)
#   * node-states=dict(str:identity, node_state)
#   * build-state=build_state
#   * all-node-output=dict(str:id: str:output)
#   * node-output-update=dict(str:id: str:output)
#
# Data structures:
# node_state:
#     last-response: iso utc datetime
#     responding: bool
#     state: str
#     package: None | (str: name, str: arch, str: version)
#     fail-reason: str
#
# build_state:
#     state: True / False
#     request: True / False
#     reason: str
#

class BuildNodeProxy(object):
    """
    Acts like a real build node but communicates via yamb>

    The current yamb address may change, of course.
    """
    def __init__(self, bm, identity, current_yamb_address):
        self.bm = bm
        self.identity = identity
        self.current_yamb_address = current_yamb_address

        self.last_response = timezone.now()
        self.last_get_status_sent = timezone.now()

        # The node's status
        self.state = None
        self.package = None
        self.fail_reason = None

        # To detect changes in response behavior for performing actions like
        # notifying the client.
        self.was_responding = False

    def request_state(self):
        logging.debug("Sending status update for node `%s'" % self.identity)
        self.bm.send_message_to_node(self.current_yamb_address, 'get_status')
        self.last_get_status_sent = timezone.now()

    def response_seen(self):
        """
        This method is to be called whenever data from this node comes in. It
        update the last_response attribute to correctly reflect the delay since
        the last response.
        """
        self.last_response = timezone.now()

    def responding(self, now = None):
        """
        Returns True if the last response is not older than 30 seconds.
        """
        if now is None:
            now = timezone.now()

        return (now - self.last_response).seconds <= 30

    def seems_dead(self, now = None):
        """
        Returns True if the last response was seen more than 600 seconds ago.
        """
        if now is None:
            now = timezone.now()

        return (now - self.last_response).seconds > 600

    def send_updates(self, now = None):
        """
        Sends an update request if the last response is considerably old. If the
        node does not respond anymore, a status update is sent to the client.
        """
        if now is None:
            now = timezone.now()

        if self.responding(now) != self.was_responding:
            self.was_responding = self.responding(now)
            self.send_state()

        update_required = False
        resp = (now - self.last_response).seconds 

        if resp > 25:
            stat = (now - self.last_get_status_sent).seconds
            if resp > 30:
                if stat > 10:
                    update_required = True
            else:
                if stat > 1:
                    update_required = True

        if update_required:
            self.request_state()

    def send_state(self, dst = None):
        if dst is None:
            dst = self.bm.current_client_addr

        if dst is not None:
            d = {
                'node-states': {
                    self.identity: {
                        'last-response': self.last_response.isoformat(),
                        'responding': self.responding(),
                        'state': self.state,
                        'package': self.package,
                        'fail-reason': self.fail_reason
                    }
                }
            }

            self.bm.send_message_to_client(dst, d)

    # Process incomming messages
    def process_state(self, state_dict):
        """
        :param state_dict: A dict containing state, name, arch, version, reason
            (the latter three may be skipped)
        """
        # The parameters of a state may change independently from the state
        # because we may have missed the state-number change.
        state = state_dict['state']
        name = state_dict.get('name')
        arch = state_dict.get('arch')
        version = state_dict.get('version')
        reason = state_dict.get('reason')

        # Convert arguments if they are present
        version = VersionNumber(version) if version is not None else version
        package = (name, arch, version)

        # Any update?
        if state != self.state or package != self.package or reason != self.fail_reason:
            self.state = state
            self.package = package
            self.fail_reason = reason

            # Send update
            self.send_state()


class BuildMaster(object):
    def __init__(self, yamb_hub_transport_addr):
        self.loop = asyncio.get_running_loop()
        self.yamb_hub_transport_addr = yamb_hub_transport_addr
        self.identity = "%s-%s" % (socket.gethostname(), timezone.now().isoformat())

        logging.info("This build master's identity: %s" % self.identity)

        # First, we need a connection to yamb
        self.yamb = yamb_node.YambNode(self.loop, self.yamb_hub_transport_addr)
        self.yamb.register_protocol (TSLB_NODE_YAMB_PROTOCOL, self.node_message_handler)
        self.yamb.register_protocol (TSLB_MASTER_CLIENT_YAMB_PROTOCOL, self.client_message_handler)

        # Second, some build nodes would be nice.
        # It's a dict(identity, proxy)
        self.build_nodes = {}

        # Start a task that cares for them and checks if they're still there
        self.loop.create_task(self.care_for_nodes())

        # Remember the last client which contacted us to send it nofitications
        self.current_client_addr = None

    async def connect(self):
        await self.yamb.connect()
        await self.yamb.wait_ready()

        self.loop.create_task(self.handle_yamb_connection_ready())

    async def handle_yamb_connection_ready(self):
        """
        Started when the connection to yamb is ready.
        """
        self.send_discover_build_nodes()

    def send_discover_build_nodes(self):
        """
        Send a discover-build-nodes message. The answers will be processed by
        the protocol handler. This avoids a request-response protocol in favour
        of a I-say-something-you-say-something like protocol that allows for
        forced updates like in ARP / ICMPv6 neighbor discovery. Hence I don't
        need to differentiate between responses and notifications.
        """
        logging.info("Sending discover-build-nodes message (action=identify)")
        self.send_message_to_node(0x80000001, 'identify')

    def send_message_to_node(self, dst, action, data={}):
        """
        Send a message to a build node.

        :param int dst:    The destination yamb address
        :param str action: The action to request the client to do
        :param dict data:  More kv-pairs to add to the message
        """
        d = dict(data)
        d['action'] = action
        self.yamb.send_yamb_message(dst, TSLB_NODE_YAMB_PROTOCOL,
                json.dumps(d).encode('utf8'))

    def node_message_handler(self, src, data):
        """
        The complementary method that is called whenever a yamb message from a
        node arrives.

        :param int src: The source yamb address
        :param bytes data: The message's data
        """
        if src == self.yamb.get_own_address():
            return

        try:
            j = json.loads(data.decode('utf8'))
            identity = j['identity']
        except Exception as e:
            logging.error("Failed to parse message from node: %s" % e)
            return

        # If we don't know about that node yet, we add it to our list
        if identity not in self.build_nodes:
            node = self.add_build_node(identity, src)
            self.send_node_list_to_client()
            node.request_state()

        else:
            # Otherwise, we do something with it.
            node = self.build_nodes[identity]
            node.response_seen()

            if 'state' in j:
                node.process_state(j)

    def add_build_node(self, identity, current_yamb_address):
        """
        Adds a build node to the list of build nodes. In case we know it already,
        the old one is overwritten.

        :param str identity: The node's identity
        :param int current_yamb_address: The node's current yamb address (from
            where we received the last message)
        :returns: The newly added build node
        """
        n = self.build_nodes[identity] = BuildNodeProxy(self, identity, current_yamb_address)
        logging.debug("Added build node `%s' at %s" % (
            identity, yamb_node.addr_to_str(current_yamb_address)))
        return n

    def remove_build_node(self, identity):
        """
        Removes a build node from the list of build nodes. If the build node is
        not in the list, nothing happens.
        """
        if identity in self.build_nodes:
            del self.build_nodes[identity]
            logging.info("Removed build node `%s'" % identity)


    # Care for the build nodes
    async def care_for_nodes(self):
        while True:
            await asyncio.sleep(1)
            now = timezone.now()

            # All this does only make sense if we are connected to yamb.
            if self.yamb.get_own_address() is not None:
                # Walk through the list of nodes and look if they need anything
                nodes = list(self.build_nodes.values())
                for node in nodes:
                    if node.seems_dead(now):
                        self.remove_build_node(node.identity)
                        self.send_node_list_to_client()

                    else:
                        node.send_updates(now)


    # Interfacing with a client
    def client_message_handler(self, src, data):
        """
        Receive a message from a requesting client.

        :param int src: The client's yamb address
        :param bytes data: The data received
        """
        if src == self.yamb.get_own_address():
            return

        try:
            j = json.loads(data.decode('utf8'))
            action = j['action']
        except Exception as e:
            logging.error('Failed to parse message from client: %s' % e)
            return

        self.current_client_addr = src

        if action == 'identify':
            self.send_message_to_client(src)
        elif action == 'request-node-list':
            self.send_node_list_to_client(src)
        elif action == 'request-node-states':
            self.send_node_states_to_client(j['nodes'], src)
        elif action == 'start-build':
            self.start_build(src)
        elif action == 'stop-build':
            self.stop_build(src)
        elif action == 'request-build-state':
            self.send_build_state(src)
        elif action == 'request-node-output':
            self.send_all_node_output(src, j['nodes'])

    def send_node_list_to_client(self, dst=None):
        """
        Send a list of node identities to the requesting client.

        :param int dst: The client's yamb address
        """
        if dst is None:
            dst = self.current_client_addr

        if dst is not None:
            nodes = [ n for n in self.build_nodes ]
            self.send_message_to_client(dst, { 'node-list': nodes })

    def send_node_states_to_client(self, nodes, dst=None):
        """
        Send a list of node states to the client.

        :param int dst: The client's yamb address
        :param list(str) nodes: A list of node identities for which the status
            is to be sent.
        """
        for identity in nodes:
            if identity in self.build_nodes:
                self.build_nodes[identity].send_state(dst)

    def start_build(self, dst):
        self.send_message_to_client(dst, {
            'build-state': {
                'state': False,
                'request': True,
                'error': 'Change requests not implemented.'
                }
            })

    def stop_build(self, dst):
        self.send_message_to_client(dst, {
            'build-state': {
                'state': False,
                'request': False
                }
            })

    def send_build_state(self, dst):
        self.send_message_to_client(dst, {
            'build-state': {
                'state': False
                }
            })

    def send_all_node_output(self, dst, nodes):
        all_node_output = {}

        for node in nodes:
            all_node_output[node] = 'Not implemented'

        self.send_message_to_client(dst, {
            'all-node-output': all_node_output})

    def send_message_to_client(self, dst, data={}):
        """
        Send a yamb message to the client.

        :param int dst: The client's yamb address
        :param dict data: Additional kv-pairs to include in the message
        """
        d = dict(data)
        d['identity'] = self.identity

        self.yamb.send_yamb_message(dst, TSLB_MASTER_CLIENT_YAMB_PROTOCOL,
                json.dumps(d).encode('utf8'))
