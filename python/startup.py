from tslb import ceph
import rbd

with ceph.ioctx(ceph._rootfs_rbd_pool) as i:
    with ceph.rbd_img(i, "220") as img:
        print(img)
