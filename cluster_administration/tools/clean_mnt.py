#!/usr/bin/env python3

import os
import re
import subprocess
from pathlib import Path

BASE = Path("/tmp/tslb")

def ensure_ret(res):
    if res.returncode != 0:
        print("cmd failed: %s." % ' '.join(res.args))
        exit(1)

def main():
    mounts = []
    with open('/proc/mounts', 'r') as f:
        for l in f:
            m = re.match(r"^\S+\s+(\S+)\s+.*$", l)
            if m:
                mounts.append(m[1])

    mounts.sort(reverse=True)

    for mount in mounts:
        # Unmount mounted scratch spaces
        if re.match("^" + re.escape(str(BASE)) + r"/rootfs/.*$", mount):
            print("unmounting '%s'." % mount)
            ensure_ret(subprocess.run(['umount', mount]))

        # Unmount mounted rootfs images
        if re.match("^" + re.escape(str(BASE)) + r"/scratch_space/.*$", mount):
            print("unmounting '%s'." % mount)
            ensure_ret(subprocess.run(['umount', mount]))

    # Remove mountpoints
    ds = list((BASE / 'scratch_space').iterdir())
    for d in (BASE / 'rootfs').iterdir():
        if d.name.startswith('.'):
            continue

        ds += list(d.iterdir())

    for d in ds:
        print("removing '%s'." % d)
        d.rmdir()

    # Unmap mapped rbd images
    rbd_maps = ['/dev/rbd' + str(i) for i in os.listdir('/sys/bus/rbd/devices')]
    for m in rbd_maps:
        print("unmapping '%s'." % m)
        ensure_ret(subprocess.run(['rbd', '-c', '/dev/null', 'unmap', m]))

if __name__ == '__main__':
    main()
