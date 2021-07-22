"""
Ceph interface for TSLB.
"""
from contextlib import contextmanager
from tslb import settings
import rados
import rbd

# Read config file
if "Ceph" not in settings:
    raise RuntimeError("No section 'Ceph' in the tslb settings file.")

for n in ["monitor", "name", "rootfs_rbd_pool", "scratch_space_rbd_pool"]:
    if n not in settings["Ceph"]:
        raise RuntimeError(
            "Key '%s' missing in section 'Ceph' of the tslb settings file." % n)

_monitor = settings["Ceph"]["monitor"]
_name = settings["Ceph"]["name"]
_rootfs_rbd_pool = settings["Ceph"]["rootfs_rbd_pool"]
_scratch_space_rbd_pool = settings["Ceph"]["scratch_space_rbd_pool"]


def get_cluster():
    c = rados.Rados(
        conffile='/dev/null',
        name=_name,
        conf={
            'mon_host': _monitor,
            'keyring': '/etc/tslb/ceph.%s.keyring' % _name
        })

    c.connect()
    return c

@contextmanager
def cluster():
    c = get_cluster()
    try:
        yield c
    finally:
        c.shutdown()


@contextmanager
def ioctx(pool):
    with cluster() as c:
        i = c.open_ioctx(pool)
        try:
            yield i
        finally:
            i.close()


get_ioctx_rootfs = lambda cluster: cluster.open_ioctx(_rootfs_rbd_pool)
ioctx_rootfs = lambda: ioctx(_rootfs_rbd_pool)


@contextmanager
def rbd_img(ioctx, name):
    img = rbd.Image(ioctx, name)
    try:
        yield img
    finally:
        img.close()
