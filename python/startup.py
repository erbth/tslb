import asyncio
import json
import yamb_node

loop = asyncio.get_event_loop()
yamb = yamb_node.YambNode(loop, 'fd00::2')

async def connect():
    await yamb.connect()
    await yamb.wait_ready()

    print("Own yamb address: %s" % yamb_node.addr_to_str(yamb.get_own_address()))

loop.run_until_complete(loop.create_task(connect()))

def send(dst, data={}):
    dst = yamb_node.str_to_addr(dst)
    yamb.send_yamb_message(dst, 1001, json.dumps(data).encode('utf8'))

def protocol_handler(src, data):
    print("Received message from %s:" % yamb_node.addr_to_str(src))
    data = json.loads(data.decode('utf8'))
    for k, v in data.items():
        print("    %s: %s" % (k, v))

yamb.register_protocol(1001, protocol_handler)

def interact():
    loop.run_until_complete(asyncio.sleep(1))
