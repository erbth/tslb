"""
Some utility functions that are useful in various conditions or special states
of the system, and do not properly fit into exactly one Python module/package.
"""
from concurrent import futures
from datetime import datetime, timezone
from tslb import Architecture
from tslb import build_pipeline
from tslb import parse_utils
from tslb import rootfs
from tslb import scratch_space
from tslb import tclm
from tslb.BinaryPackage import BinaryPackage
from tslb.SourcePackage import SourcePackage, SourcePackageList, SourcePackageVersion
from tslb.tclm import lock_X
import os
import re

# Compatibility
from tslb.basic_utils import *


def initially_create_all_locks():
    """
    Creates all locks at the tclm. Useful to populate them when starting the
    system.
    """
    # Create locks for scratch spaces
    scratch_space.create_locks()

    # Create locks for packages
    for arch in Architecture.architectures.keys():
        spl = SourcePackageList(arch, create_locks = True)

        sps = spl.list_source_packages()

        with lock_X(spl.db_root_lock):
            for n in sps:
                p = SourcePackage(n, arch, create_locks=True, write_intent=True)

                for v in p.list_version_numbers():
                    spv = SourcePackageVersion(p, v, create_locks=True)

                    for bn in spv.list_all_binary_packages():
                        for bv in spv.list_binary_package_version_numbers(bn):
                            BinaryPackage(spv, bn, bv, create_locks=True)


    # Create locks for rootfs images
    lk = tclm.define_lock('tslb.rootfs.available')
    lk.create(True)
    lk.release_X()

    rlk = tclm.define_lock('tslb.rootfs.images')
    rlk.create(True)

    try:
        for i in rootfs.list_images():
            tclm.define_lock('tslb.rootfs.images.' + str(i)).create(False)

    finally:
        rlk.release_X()


def run_bash_in_rootfs_image(img_id):
    """
    Start an interactive bash shell in an isolated (not sharing environment)
    chroot environment rooted at the given image.

    :param img_id: The rootfs image's id
    :returns: The shell's return code
    :raises rootfs.NoSuchImage: If the id does not match an image
    """
    img_id = int(img_id)
    image = rootfs.Image(img_id)

    if not image.in_available_list:
        # Upgrade to an X lock
        lk = tclm.define_lock('tslb.rootfs.images.%d' % img_id)
        lk.acquire_Splus()

        del image
        lk.acquire_X()
        lk.release_Splus()

        image = rootfs.Image(img_id, acquired_X=True)

    mount_namespace = 'manual'

    image.mount(mount_namespace)
    mountpoint = image.get_mountpoint(mount_namespace)

    # Avoid a cyclic import dependency
    from tslb import package_builder as pb

    try:
        pb.mount_pseudo_filesystems(mountpoint)

        def f():
            return os.execlp('bash', 'bash', '--login', '+h')

        return pb.execute_in_chroot(mountpoint, f)

    finally:
        pb.unmount_pseudo_filesystems(mountpoint, raises=True)
        image.unmount(mount_namespace)


def remove_old_snapshots_from_scratch_space(space, keep, print_fn=None):
    """
    Remove 'old' snapshots from a scratch space; i.e. snapshots of a build
    pipeline stage that does not exist anymore or where :param keep: newer
    snapshots of that build pipeline stage exist. Note that at least one
    snapshot of each stage is kept, hence settings keep < 1 results in a
    ValueError.

    This requires an X lock on the scratch space (it must be created with `rw =
    True`) and that the scratch space is not mounted.

    :param ScratchSpace space:
    :param int keep: Number of snapshots to keep of each stage.
    :param print_fn: An optional callable that will be called on each snapshot
        before it is removed. It receives the snapshot's name as argument. It
        may be used to e.g. print which snapshots are removed.

    :raises ValueError: If keep < 1
    :raises scratch_space.NotWritable: If the space does not have an X lock
    :raises ScratchSpaceMounted: If the scratch space is mounted
    """
    if keep < 1:
        raise ValueError("At least one snapshot of each build pipeline stage "
                "must be kept.")

    if not space.rw:
        raise scratch_space.NotWritable

    if space.mounted:
        raise ScratchSpaceMounted

    # Find such snapshots
    to_remove = []
    stage_snapshots = { s.name: [] for s in build_pipeline.all_stages }

    for snap in space.list_snapshots():
        m = re.match(r'^(.*)-(\d+-\d+-[^-]+)$', snap)
        if not m or m[1] not in stage_snapshots:
            to_remove.append(snap)
            continue

        stage_snapshots[m[1]].append(
                (datetime.fromisoformat(m[2]).replace(tzinfo=timezone.utc), snap))

    for snaps in stage_snapshots.values():
        snaps.sort()
        snaps.reverse()
        to_remove += [t[1] for t in snaps[keep:]]

    # Remove snapshots
    for snap in to_remove:
        if print_fn:
            print_fn(snap)

        space.delete_snapshot(snap)


def remove_old_snapshots_from_scratch_spaces_in_arch(arch, keep, print_fn=None):
    """
    Remove 'old' snapshots (see `remove_old_snapshots_from_scratch_space`) from
    all scratch spaces that are associated with the given architecture.

    :param arch:
    :param int keep:
    :param print_fn: Will receive scratch space and snapshot names of each
        snapshot as arguments before it is deleted.
    """
    to_process = []

    for name in scratch_space.ScratchSpacePool().list_scratch_spaces():
        m = re.match(r'^.+_([^_]+)_[^_]+$', name)
        if m and m[1] == Architecture.to_str(arch):
            to_process.append(name)

    with futures.ThreadPoolExecutor(5) as exe:
        def work(name):
            space = scratch_space.ScratchSpace(
                    scratch_space.ScratchSpacePool(),
                    name,
                    True)

            remove_old_snapshots_from_scratch_space(space, keep,
                    print_fn=(lambda sn: print_fn(name, sn)) if print_fn else None)

        fs = [exe.submit(work, name) for name in to_process]
        res = futures.wait(fs, return_when=futures.ALL_COMPLETED)

        # Let potential exceptions occur
        for r in res.done:
            r.result()


def is_source_package_enabled(sp):
    """
    :param SourcePackage:
    :returns bool: True if the source package has at least one enabled version
    """
    for v in sp.list_version_numbers():
        spv = sp.get_version(v)
        if spv.has_attribute('enabled') and parse_utils.is_yes(spv.get_attribute('enabled')):
            return True

    return False


def list_enabled_source_packages(spl):
    """
    Given a `SourcePackageList` :param spl: list all source packages in the
    list's architecture that have at least one enabled version.

    :rtype: Sequence(str)
    """
    l = []
    for pkg in spl.list_source_packages():
        if is_source_package_enabled(SourcePackage(pkg, spl.architecture)):
            l.append(pkg)

    return l


#*********************************** Exceptions *******************************
class ScratchSpaceMounted(Exception):
    def __init__(self):
        super().__init__("Scratch space is mounted.")
