import asyncio
import json
import logging
import yamb_node
from tslb.build_master import TSLB_MASTER_CLIENT_YAMB_PROTOCOL
from tslb import timezone
from tslb.VersionNumber import VersionNumber
from tslb.stream import stream
from tslb.client_proxy import message

class BuildNodeProxy(object):
    def __init__(self, master, identity):
        self.master = master
        self.identity = identity

        # The node's state (read from the build master)
        self.last_response = None
        self.responding = False
        self.state = None
        self.package = None
        self.fail_reason = None

    def request_status(self):
        self.master.send_message('request-node-states', { 'nodes': [ self.identity ] })

    def process_state(self, node_state):
        """
        :param node_state: dict containing last-response, responding, state, 
            package, fail-reason
        """
        last_response = node_state['last-response']
        responding = node_state['responding']
        state = node_state['state']
        name, arch, version = node_state['package']
        fail_reason = node_state['fail-reason']

        # Parse parameters
        version = VersionNumber(version) if version is not None else version
        package = (name, arch, version)

        if last_response != self.last_response or\
                responding != self.responding or\
                state != self.state or\
                package != self.package or\
                fail_reason != self.fail_reason:

            self.last_response = last_response
            self.responding = responding
            self.state = state
            self.package = package
            self.fail_reason = fail_reason

            logging.debug("Build node [%s]: State changed: %s / %s - %s" %
                    (self.identity, self.last_response, self.responding, self.state))

class BuildMasterProxy(object):
    """
    The BuildMasterProxy does not only hold a build master's attributes but also
    inform clients about status changes.
    """
    def __init__(self, mgr, identity, current_yamb_address):
        self.mgr = mgr
        self.identity = identity
        self.current_yamb_address = current_yamb_address

        # To determine if this build master is alive
        self.last_contact = None

        # Build nodes discovered and managed by this master
        # dict(identity, node)
        self.build_nodes = {}

    def update_current_yamb_address(self, addr):
        self.current_yamb_address = addr

    def seems_dead(self, now = None):
        if now is None:
            now = timezone.now()

        return (now - self.last_contact).total_seconds() > 30

    def response_seen(self, now = None):
        if now is None:
            now = timezone.now()

        self.last_contact = now

    def send_updates(self, now=None):
        """
        Send various status update requests, when they are needed. This routine
        assumes that we are connected to the yamb.

        :param datetime.datetime now: The current time.
        """
        if now is None:
            now = timezone.now()

        if self.last_contact is None:
            # Request a list of nodes and the build state
            self.request_node_list()
            self.request_build_state()

        elif (now - self.last_contact).total_seconds() > 25:
            # Ping
            self.request_identity()

    def request_identity(self):
        logging.debug('Ping build master ...')
        self.send_message(action='identify')

    def request_node_list(self):
        logging.debug('Requesting node list')
        self.send_message(action='request-node-list')

    def request_build_state(self):
        logging.debug('Requesting build state')
        self.send_message(action='request-build-state')

    def send_message(self, action, data={}):
        self.mgr.send_message_to_build_master(self.current_yamb_address, action, data)

    # Process incomming data (includes sending messages to clients)
    def process_node_list(self, nodes):
        """
        :param nodes: list of node identities as strings.
        """
        logging.debug ("Received node list: %s" % nodes)

        new_names = set(nodes)
        old_names = set(self.build_nodes)

        removed_names = old_names - new_names
        added_names = new_names - old_names

        for n in removed_names:
            del self.build_nodes[n]
            logging.debug('Build node %s deleted' % n)

        for n in added_names:
            node = self.build_nodes[n] = BuildNodeProxy(self, n)
            node.request_status()
            logging.debug('Build node %s added' % n)

    def process_node_states(self, node_states):
        """
        :param node_states: { identity: { node state } }
        """
        for n in node_states:
            node = self.build_nodes.get(n)

            if node:
                node.process_state(node_states[n])

    def process_build_state(self, build_state):
        """
        :param build_state: Build state as dict with state, request, request-error
        """
        logging.debug("Received build state: %s" % build_state)

class Client(object):
    """
    Stores a client connection and processes incomming messages.
    """
    def __init__(self, client_proxy, reader, writer):
        self.client_proxy = client_proxy
        self.reader = reader
        self.writer = writer

        # Start a read loop
        asyncio.get_running_loop().create_task(self.read_loop())

    async def read_loop(self):
        buf = stream()

        while True:
            try:
                data = await self.reader.read(10000)
            except Exception as e:
                logging.debug("Client connection closed due to: %s." % e)
                break
            except:
                logging.debug("Client connection closed due to unknown error.")
                break

            if data == b'':
                break

            buf.write_bytes(data)

            l = message.contains_full(buf)
            if l:
                msg = buf.pop(l)
                self.process_message(msg)

        # Remove the client
        self.client_proxy.remove_client(self)

    def process_message(self, msg):
        msgid, length = message.parse(msg)

        if msgid == 1:
            if self.client_proxy.build_master is not None:
                msg = message.create_build_master_update((
                    self.client_proxy.build_master.identity,
                    self.client_proxy.build_master.current_yamb_address,
                    self.client_proxy.build_master.seems_dead()
                    ))
            else:
                msg = message.create_build_master_update()

            self.send_stream(msg)

        elif msgid == 2:
            logging.debug('get_node_list')

        elif msgid == 3:
            try:
                name = message.parse_get_node_state(msg)
            except message.ParseError as e:
                logging.error(str(e))

            else:
                logging.debug('get_node_state(%s)' % name)

        else:
            logging.error("Received unknown message with msgid = %d." % msgid)

    def send_stream(self, s):
        self.writer.write(s.buffer)

class ClientProxy(object):
    def __init__(self, yamb_hub_transport_addr):
        self.loop = asyncio.get_running_loop()
        self.yamb_hub_transport_addr = yamb_hub_transport_addr

        # First, we need a connection to yamb
        self.yamb = yamb_node.YambNode(self.loop, self.yamb_hub_transport_addr)
        self.yamb.register_protocol (TSLB_MASTER_CLIENT_YAMB_PROTOCOL, self.build_master_message_handler)

        # Second, we need to interface with a build master if one exists.
        self.build_master = None

        # Start a task that cares for periodic status updates.
        self.loop.create_task(self.periodic_updates())

        # Finally we should communicate with clients.
        self.client_server = None
        self.loop.create_task(self.start_server())

        self.clients = set()

    async def start_server(self):
        self.client_server = await asyncio.start_server(self.handle_client_connect, '::', 30100)
        await self.client_server.start_serving()

    async def connect(self):
        # Connect to yamb
        await self.yamb.connect()
        await self.yamb.wait_ready()

        self.loop.create_task(self.handle_yamb_connection_ready())

    async def handle_yamb_connection_ready(self):
        """
        Started when the connection to yamb is ready.
        """
        if self.build_master is None:
            self.send_discover_build_master()

    def send_discover_build_master(self):
        """
        Send a discover-build-master message.
        """
        logging.info("Sending a discover-build-master message (action=identify)")
        self.send_message_to_build_master(0x80000001, 'identify')

    def send_message_to_build_master(self, dst, action, data={}):
        """
        Send a messate to a build master.

        :param int dst:    The destination yamb address
        :param str action: The action to request the build master to do
        :param dict data:  More kv-pairs to add to the message
        """
        d = dict(data)
        d['action'] = action
        self.yamb.send_yamb_message(dst, TSLB_MASTER_CLIENT_YAMB_PROTOCOL,
                json.dumps(d).encode('utf8'))

    def build_master_message_handler(self, src, data):
        """
        The complementary method that is called whenever a yamb message from a
        build master arrives.

        :param int src: The source yamb address
        :param bytes data: The message's data
        """
        if src == self.yamb.get_own_address():
            return

        try:
            j = json.loads(data.decode('utf8'))
            identity = j['identity']
        except Exception as e:
            logging.error("Failed to parse message from build master: %s" % e)
            return

        # If we don't know a build master yet, take this one.
        if self.build_master is None:
            self.build_master = BuildMasterProxy(self, identity, src)
            logging.info("Found a new build master: %s@%s" %
                    (self.build_master.identity,
                        yamb_node.addr_to_str(self.build_master.current_yamb_address)))

            self.build_master.send_updates()

        elif self.build_master.identity != identity:
            # If that is not our build master, ignore the message
            return

        # It's a message from our build master.
        self.build_master.response_seen()

        if 'node-list' in j:
            self.build_master.process_node_list(j['node-list'])

        if 'build-state' in j:
            self.build_master.process_build_state(j['build-state'])

        if 'node-states' in j:
            self.build_master.process_node_states(j['node-states'])

    # Client connections
    def remove_client(self, client):
        self.clients.remove(client)
        client.writer.close()

    async def handle_client_connect(self, reader, writer):
        self.clients.add(Client(self, reader, writer))

    # Do periodic updates
    async def periodic_updates(self):
        while True:
            await asyncio.sleep(1)
            now = timezone.now()

            # All this does only make sense if we are connected to yamb.
            if self.yamb.get_own_address() is not None:
                if self.build_master is None:
                    self.send_discover_build_master()

                else:
                    if self.build_master.seems_dead():
                        logging.info("Current build master %s seems dead, removing." %
                                self.build_master.identity)
                        self.build_master = None

                    else:
                        self.build_master.send_updates(now)
