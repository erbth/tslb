import asyncio
import yamb_node
from tslb.build_master import bm_interface
from tslb.build_master import client_interface


# The main entrypoint of the build master
class BuildMaster:
    """
    The main entrypoint and controlling entity of the build master.
    """
    def __init__(self, loop, lsr, yamb_hub_transport_address, identity):
        """
        :param lsr: LoopStopReson to be set on error
        :type lsr: something with set_code and get_code methods.
        """
        self._yamb = yamb_node.YambNode(loop, yamb_hub_transport_address)
        self._loop = loop
        self._lsr = lsr
        self._lsr.set_code(0)

        self._identity = identity

        self._controller = bm_interface.MockController(self._loop, self._identity)
        self._client_interface = client_interface.ClientInterface(loop, self._yamb, self._controller)


    async def connect_to_yamb_hub(self):
        try:
            await self._yamb.connect()
            await self._yamb.wait_ready()
        except BaseException as e:
            print(e)
            await self.request_quit()
            self._lsr.set_code(1)
            return

        print ("Connected to yamb with node address %s." %
                yamb_node.addr_to_str(self._yamb.get_own_address()))


    async def request_quit(self):
        print ("Stopping")

        # Stop all remaining tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

        for task in tasks:
            print("Cancelling task `%r'." % task)
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        self._loop.stop()
