from Architecture import architectures, architectures_reverse
from build_pipeline import BuildPipeline
from Console import Color
from VersionNumber import VersionNumber
import SourcePackage
import asyncio
import json
import multiprocessing
import os
import processes
import socket
import yamb_node
from build_node import TSLB_NODE_YAMB_PROTOCOL

# State definitions
# Packages are triples (name, arch, version)
STATE_IDLE          = 0     # (., )
STATE_BUILDING      = 1     # (., package)
STATE_FAILED        = 2     # (., package, reason)
STATE_FINISHED      = 3     # (., package)
STATE_MAINTENANCE   = 4     # (., )

FAIL_REASON_NODE_TRY_AGAIN  = 0
FAIL_REASON_NODE_ABORT      = 1
FAIL_REASON_PACKAGE         = 2

reason_to_str = {
        FAIL_REASON_NODE_TRY_AGAIN: 'node/try_again',
        FAIL_REASON_NODE_ABORT: 'node/abort',
        FAIL_REASON_PACKAGE: 'package'
        }

def build_package_worker(self, name, arch, version_number, error, finished_event):
    """
    This function is to be run in an extra process. It builds a package and
    reports the result in the error shared mulitprocessing.Value. It may
    place -1 there, in which case the build succeeded, or any of FAIL_REASON_*
    defined above.

    :param name: The package's name
    :type name: str
    :param arch: The package's architecture
    :type arch: int
    :param version_number: The package's version number
    :type version_number: VersionNumber.VersionNumber
    :param error: A variable to receive a potential error code
    :type error: multiprocessing.Value
    :param finished_event: An event to be set just before the process will finish
    :type finished_event: asyncio.Event
    """
    print("Building Source Package %s:%s@%s" % (name, version_number, architectures[arch]))

    # Find the package version
    try:
        spkg = SourcePackage.SourcePackage(name, arch, write_intent=True)
        spv = spkg.get_version(version_number)
    except Exception as e:
        print(e)
        error.value = FAIL_REASON_PACKAGE
        finished_event.set()
        return
    except:
        error.value = FAIL_REASON_PACKAGE
        finished_event.set()
        return

    # Build the package
    bp = BuildPipeline()

    if bp.build_source_package_version(spv):
        print(Color.GREEN + "Completed successfully." + Color.NORMAL)
        error.value = -1
    else:
        print(Color.RED + "FAILED." + Color.NORMAL)
        error.value = FAIL_REASON_PACKAGE

    finished_event.set()

class BuildNode(object):
    def __init__(self, loop, lsr, yamb_hub_transport_address):
        """
        :param lsr: LoopStopReason to be set on error
        :type lsr: something with set_code and get_code methods.
        """
        self.yamb = yamb_node.YambNode(loop, yamb_hub_transport_address)
        self.yamb.register_protocol(TSLB_NODE_YAMB_PROTOCOL, self.protocol_handler)
        self.loop = loop
        self.lsr = lsr

        number = len(processes.list_matching('^' + processes.name_from_pid(os.getpid()) + '$')) - 1
        self.identity = "%s:%d" % (socket.gethostname(), number)
        print ("Own identity: %s" % self.identity, flush=True)

        self.state = (STATE_IDLE,)
        self.build_master_addr = None

        # A worker process and its monitor task
        self.worker_error = multiprocessing.Value('i', FAIL_REASON_NODE_ABORT)
        self.worker_process = None
        self.worker_monitor = self.loop.create_task(self.worker_monitor_function())
        self.worker_finished_event = asyncio.Event()

    async def connect_to_yamb_hub(self):
        try:
            await self.yamb.connect()
            await self.yamb.wait_ready()
        except Exception as e:
            print(e)
            self.loop.stop()
            self.lsr.set_code(1)
            return
        except:
            self.loop.stop()
            self.lsr.set_code(1)
            return

        print ("Connected to yamb with node address %s." %
                yamb_node.addr_to_str(self.yamb.get_own_address()))

    def request_quit(self):
        print ("Stopping")
        self.worker_monitor.cancel()
        self.loop.stop()

    # Send a message to the build master
    def send_message_to_master(self, dst, data={}):
        """
        Send a message to the build master that includes our own identity.

        :param int dst: The build master's address
        :param dict data: The data to send as kv-pairs.
        """
        d = dict(data)
        d['identity'] = self.identity

        self.yamb.send_yamb_message(dst, TSLB_NODE_YAMB_PROTOCOL,
                json.dumps(d).encode('utf8'))

    # Look after the worker process
    async def worker_monitor_function(self):
        while True:
            killed = False
            exited = False

            await self.worker_finished_event.wait()
            if self.worker_finished_event.get():
                self.worker_finished_event.reset()

                # Give the worker time to exit after it set the event
                self.worker_process.join(timeout=5)

                if self.worker_process.exit_code is not None:
                    # The worker has finished!
                    exited = True
                else:
                    # It appears to hang. Kill it ...
                    self.worker_process.kill()
                    killed = True
                    print(Color.RED + "The worker process hung. Killed it." + Color.NORMAL)

            # Change state and send notifications
            # self.build_master_addr will not be None because someone must have
            # initiated the build.
            if killed:
                # -> failed
                self.state = (STATE_FAILED, self.state[1], FAIL_REASON_NODE_ABORT)

                name, arch, version = self.state[1]
                self.send_message_to_master (self.build_master_addr, {
                        'state': 'failed',
                        'name': name,
                        'arch': architectures[arch],
                        'version': version,
                        'reason': 'node/abort'
                        })

            elif exited:
                if self.worker_error.value >= 0:
                    # -> failed
                    self.state = (STATE_FAILED, self.state[1], self.worker_error.value)

                    name, arch, version = self.state[1]
                    reason = reason_to_str[self.state[2]]
                    d = {
                            'state': 'failed',
                            'name': name,
                            'arch': architectures[arch],
                            'version': version,
                            'reason': reason
                            }
                else:
                    # -> finished
                    self.state = (STATE_FINISHED, self.state[1])
                    name, arch, version = self.state[1]
                    d = {
                            'state': 'finished',
                            'name': name,
                            'arch': architectures[arch],
                            'version': version,
                            }

                self.send_message_to_master(self.build_master_addr, d)

            # Clean up.
            # killed or exited will only be True if the process stopped in this
            # iteration of the loop a few lines above.
            if killed or exited:
                self.worker_process.close()
                self.worker_process = None

    # Interacting with the build master
    def start_build(self, name, arch, version, dst):
        self.state = (STATE_BUILDING, (name, arch, version))
        self.build_master_addr = dst

        try:
            self.worker_process = multiprocessing.Process(target=build_package_worker,
                    args=(name, arch, version, self.worker_error, self.worker_finished_event))
            self.worker_process.start()

        except Exception as e:
            self.abort_build(dst)
            return

        self.send_message_to_master(dst, {
            'state': 'building',
            'name': name,
            'arch': architectures[arch],
            'version': version
            })

    def abort_build(self, dst):
        self.state = (STATE_FAILED, (name, arch, version), FAIL_REASON_NODE_ABORT)

        if self.worker_process is not None:
            if self.worker_process.is_alive():
                self.worker_process.kill()

            self.worker_process.close()
            self.worker_process = None

        self.send_message_to_master(dst, {
            'state': 'failed',
            'name': name,
            'arch': architectures[arch],
            'version': version,
            'reason': 'node/abort'
            })

    def get_status(self, dst):
        s = self.state[0]
        d = None

        if s == STATE_IDLE:
            d = {
                    'state': 'idle'
                    }

        elif s == STATE_BUILDING:
            name, arch, version = self.state[1]
            d = {
                    'state': 'building',
                    'name': name,
                    'arch': architectures[arch],
                    'version': version,
                    }

        elif s == STATE_FAILED:
            name, arch, version = self.state[1]
            reason = reason_to_str[self.state[2]]
            d = {
                    'state': 'failed',
                    'name': name,
                    'arch': architectures[arch],
                    'version': version,
                    'reason': reason
                    }

        elif s == STATE_FINISHED:
            name, arch, version = self.state[1]
            d = {
                    'state': 'finished',
                    'name': name,
                    'arch': architectures[arch],
                    'version': version,
                    }

        elif s == STATE_MAINTENANCE:
            d = {
                    'state': 'maintenance'
                    }

        if d is not None:
            self.send_message_to_master(dst, d)

    def identify(self, dst):
        # Our own identity will be included automatically
        self.send_message_to_master(dst)

    def enable_maintenance(self, force, dst):
        pass

    def disable_maintenance(self, dst):
        pass

    def get_load(self):
        pass

    def protocol_handler(self, src, data):
        if src != self.yamb.get_own_address():
            try:
                j = json.loads(data.decode('utf8'))

                action = j['action']
            except:
                return

            if action == 'identify':
                self.identify(src)

            elif action == 'start_build':
                try:
                    name = j['name']
                    arch = architectures_reverse[j['arch']]
                    version = VersionNumber(j['version'])
                except:
                    return

                self.start_build(name, arch, version, src)

            elif action == 'get_status':
                self.get_status(src)

            elif action == 'abort_build':
                self.abort_build(src)
