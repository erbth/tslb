import asyncio
import queue
from tslb import settings
import yamb_node

class YambConnection(object):
    def __init__(self):
        # Parse configuration data.
        if 'Yamb' not in settings:
            raise Exception('Missing section `Yamb\' in system configuration file.')

        self.yamb_hub_transport_address = settings['Yamb'].get('hub', None)
        if not self.yamb_hub_transport_address:
            raise Exception('No yamb hub transport address specified in the system configuration file.')

        # Create a main loop and an init task
        self.loop = asyncio.new_event_loop()
        self.loop.create_task(self.init())

    def run_main_loop(self):
        # Run the main loop
        self.loop.run_forever()

    async def init(self):
        self.yamb = yamb_node.YambNode(self.loop, self.yamb_hub_transport_address)
        await self.yamb.connect()
        await self.yamb.wait_ready()

    async def exit_gracefully(loop, reason=None):
        tasks = [ t for t in asyncio.all_tasks() if t is not asyncio.current_task() ]
        for t in tasks:
            t.cancel()

        loop.stop()
