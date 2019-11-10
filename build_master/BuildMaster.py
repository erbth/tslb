import asyncio
import json
import logging
import yamb_node
from build_node import TSLB_NODE_YAMB_PROTOCOL
from build_master import TSLB_MASTER_CLIENT_YAMB_PROTOCOL
import timezone

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
#   * action=discover: Just to find the master's yamb address
#   * action=request-node-list
#   * action=request-node-state, node_identity=<identity:str>
#
# Master -> Client messages:
# These maybe completely empty if they are just to tell our yamb address.
#   * node-list=list(node identities:str)
#   * node-states=list(node_state)
#
# Data structures:
# node_state:
#     identity: str
#     last-response: iso utc datetime
#     responding: bool

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

    def send_get_status(self):
        logging.info("Sending status update for node `%s'" % self.identity)
        self.bm.send_message_to_node(self.current_yamb_address, 'get_status')
        self.last_get_status_sent = timezone.now()

    def response_seen(self):
        """
        This method is to be called whenever data from this node comes in. It
        update the last_response attribute to correctly reflect the delay since
        the last response.
        """
        self.last_response = timezone.now()

    def responding(self):
        """
        Returns True if the last response is not older than 30 seconds.
        """
        return (timezone.now() - self.last_response).seconds <= 30

    def seems_dead(self):
        """
        Returns True if the last response was seen more than 600 seconds ago.
        """
        return (timezone.now() - self.last_response).seconds > 600

    def status_update_required(self):
        """
        Returns True if the last response is older than 25 seconds and the last
        status request was sent more than 1 second ago until the last response
        is older than 30 seconds, where the probing interval will be 10 seconds,
        then.
        """
        now = timezone.now()
        resp = (now - self.last_response).seconds 

        if resp > 25:
            stat = (now - self.last_get_status_sent).seconds
            if resp > 30:
                if stat > 10:
                    return True
            else:
                if stat > 1:
                    return True

        return False


class BuildMaster(object):
    def __init__(self, yamb_hub_transport_addr):
        self.loop = asyncio.get_running_loop()
        self.yamb_hub_transport_addr = yamb_hub_transport_addr

        # First, we need a connectio to yamb
        self.yamb = yamb_node.YambNode(self.loop, self.yamb_hub_transport_addr)
        self.yamb.register_protocol (TSLB_NODE_YAMB_PROTOCOL, self.node_message_handler)
        self.yamb.register_protocol (TSLB_MASTER_CLIENT_YAMB_PROTOCOL, self.client_message_handler)

        # Second, some build nodes would be nice.
        # It's a dict(identity, proxy)
        self.build_nodes = {}

        # Start a task that cares for them and check if they're still there
        self.loop.create_task(self.care_for_nodes())

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
            self.add_build_node(identity, src)

        else:
            # Otherwise, we do something with it.
            node = self.build_nodes[identity]
            node.response_seen()

    def add_build_node(self, identity, current_yamb_address):
        """
        Adds a build node to the list of build nodes. In case we know it already,
        the old one is overwritten.

        :param str identity: The node's identity
        :param int current_yamb_address: The node's current yamb address (from
            where we received the last message)
        """
        self.build_nodes[identity] = BuildNodeProxy(self, identity, current_yamb_address)
        logging.info("Added build node `%s' at %s" % (
            identity, yamb_node.addr_to_str(current_yamb_address)))

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

            # All this does only make sense if we are connected to yamb.
            if self.yamb.get_own_address() is not None:
                # Walk through the list of nodes and look if they need anything
                nodes = list(self.build_nodes.values())
                for node in nodes:
                    if node.seems_dead():
                        self.remove_build_node(node.identity)

                    elif node.status_update_required():
                        node.send_get_status()


    # Interfacing with a client
    async def client_message_handler(self, src, data):
        """
        Receive a message from a requesting client.

        :param int src: The client's yamb address
        :param bytes data: The data received
        """
        if src == self.yamb.get_own_addres():
            return

        try:
            j = json.loads(data.decode('utf8'))
            action = j['action']
        except Exception as e:
            logging.error('Failed to parse message from client: %s' % e)
            return

        if action == 'request-node-list':
            self.send_node_list_to_client(src)
        elif action == 'request-node-state':
            self.send_node_states_to_client(src, (j['identity'],))

    def send_node_list_to_client(self, dst):
        """
        Send a list of node identities to the requesting client.

        :param int dst: The client's yamb address
        """
        nodes = [ n.identity for n in self.build_nodes ]
        self.send_message_to_client(dst, { 'node-list': nodes })

    def send_node_state_to_client(self, dst, nodes):
        """
        Send a list of node states to the client.

        :param int dst: The client's yamb address
        :param list(str) nodes: A list of node identities for which the status
            is to be sent.
        """
        states = []

        for identity in nodes:
            if identity in self.build_node:
                node = self.build_nodes[identity]

                states.append({
                    'identity': identity,
                    'last-response': node.last_response.isoformat(),
                    'responding': node.responding()
                    })

        self.send_message_to_client(dst, { 'node-states': states })

    def send_message_to_client(self, dst, data={}):
        """
        Send a yamb message to the client.

        :param int dst: The client's yamb address
        :param dict data: Additional kv-pairs to include in the message
        """
        self.yamb.send_yamb_message(dst, YAMB_MASTER_CLIENT_YAMB_PROTOCOL,
                json.dumps(data).encode('utf8'))
