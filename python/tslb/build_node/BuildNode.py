from tslb import SourcePackage
from tslb import processes
from tslb.Architecture import architectures, architectures_reverse
from tslb.Console import Color
from tslb.VersionNumber import VersionNumber
from tslb.build_node import TSLB_NODE_YAMB_PROTOCOL
from tslb.build_pipeline import BuildPipeline
import asyncio
import json
import multiprocessing, aioprocessing
import os
import socket
import time
import yamb_node

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

state_to_str = {
        STATE_IDLE: 'idle',
        STATE_BUILDING: 'building',
        STATE_FAILED: 'failed',
        STATE_FINISHED: 'finished',
        STATE_MAINTENANCE: 'maintenance'
        }

reason_to_str = {
        FAIL_REASON_NODE_TRY_AGAIN: 'node/try_again',
        FAIL_REASON_NODE_ABORT: 'node/abort',
        FAIL_REASON_PACKAGE: 'package'
        }

def build_package_worker(self, name, arch, version_number, error):
    """
    This function is to be run in an extra process. It builds a package and
    reports the result in the error shared multiprocessing.Value. It may
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
    """
    print("Building Source Package %s:%s@%s" % (name, version_number, architectures[arch]))

    time.sleep(5)
    error.value = -1
    print("done.")
    return

    # Find the package version
    try:
        spkg = SourcePackage.SourcePackage(name, arch, write_intent=True)
        spv = spkg.get_version(version_number)
    except Exception as e:
        print(e)
        error.value = FAIL_REASON_PACKAGE
        return
    except:
        error.value = FAIL_REASON_PACKAGE
        return

    # Build the package
    bp = BuildPipeline()

    if bp.build_source_package_version(spv):
        print(Color.GREEN + "Completed successfully." + Color.NORMAL)
        error.value = -1
    else:
        print(Color.RED + "FAILED." + Color.NORMAL)
        error.value = FAIL_REASON_PACKAGE

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
        self.worker_monitor = None

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
        if self.worker_monitor:
            self.worker_monitor.cancel()

        if self.worker_process:
            self.worker_process.kill()
            print(Color.RED + "Killed the worker process." + Color.NORMAL)

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

    async def worker_monitor_function(self):
        """
        Look after the worker process
        """
        killed = False
        exited = False

        # Wait for worker process
        await self.worker_process.coro_join()

        if self.worker_error.value == -2:
            # The worker did not alter this value and hence must have been
            # killed ...
            killed = True
        else:
            # The worker has finished!
            exited = True

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
                    'version': str(version),
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
                        'version': str(version),
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
                        'version': str(version),
                        }

            self.send_message_to_master(self.build_master_addr, d)

        # Clean up.
        self.worker_process.close()
        self.worker_process = None
        self.worker_monitor = None

    # Interacting with the build master
    def start_build(self, name, arch, version, dst):
        if self.state[0] == STATE_IDLE:
            self.state = (STATE_BUILDING, (name, arch, version))
            self.build_master_addr = dst

            self.worker_error.value = -2

            try:
                self.worker_process = aioprocessing.AioProcess(target=build_package_worker,
                        args=(self, name, arch, version, self.worker_error))
                self.worker_process.start()

                self.loop.create_task(self.worker_monitor_function())

            except Exception as e:
                self.abort_build(dst)
                return

            self.send_message_to_master(dst, {
                'state': 'building',
                'name': name,
                'arch': architectures[arch],
                'version': str(version)
                })

        else:
            self.send_message_to_master(dst, {
                'err': 'Action `start_build\' not applicable in state %s.' % state_to_str[self.state[0]]
                })

    def abort_build(self, dst):
        if self.state[0] == STATE_BUILDING:
            name, arch, version = self.state[1]
            self.state = (STATE_FAILED, (name, arch, version), FAIL_REASON_NODE_ABORT)

            if self.worker_process is not None:
                if self.worker_process.is_alive():
                    self.worker_process.kill()

        else:
            self.send_message_to_master(dst, {
                'err': 'Action `abort\' not applicable in state %s.' % state_to_str[self.state[0]]
                })

    def reset(self, dst):
        if self.state[0] == STATE_FINISHED or self.state[0] == STATE_FAILED or\
                self.state[0] == STATE_IDLE:

            self.state = (STATE_IDLE,)

            self.send_message_to_master(dst, {
                'state': 'idle',
                })

        else:
            self.send_message_to_master(dst, {
                'err': 'Action `reset\' not applicable in state %s.' % state_to_str[self.state[0]]
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
                    'version': str(version),
                    }

        elif s == STATE_FAILED:
            name, arch, version = self.state[1]
            reason = reason_to_str[self.state[2]]
            d = {
                    'state': 'failed',
                    'name': name,
                    'arch': architectures[arch],
                    'version': str(version),
                    'reason': reason
                    }

        elif s == STATE_FINISHED:
            name, arch, version = self.state[1]
            d = {
                    'state': 'finished',
                    'name': name,
                    'arch': architectures[arch],
                    'version': str(version),
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

    def enable_maintenance(self, dst):
        if self.state[0] == STATE_IDLE:
            self.state = (STATE_MAINTENANCE,)

            self.send_message_to_master(dst, {
                'state': 'maintenance',
                })

        else:
            self.send_message_to_master(dst, {
                'err': 'Action `enable_maintenance\' not applicable in state %s.' % state_to_str[self.state[0]]
                })

    def disable_maintenance(self, dst):
        if self.state[0] == STATE_MAINTENANCE:
            self.state = (STATE_IDLE,)

            self.send_message_to_master(dst, {
                'state': 'idle',
                })

        else:
            self.send_message_to_master(dst, {
                'err': 'Action `disable_maintenance\' not applicable in state %s.' % state_to_str[self.state[0]]
                })

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

            elif action == 'reset':
                self.reset(src)

            elif action == 'enable_maintenance':
                self.enable_maintenance(src)

            elif action == 'disable_maintenance':
                self.disable_maintenance(src)
