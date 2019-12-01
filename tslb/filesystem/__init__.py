"""
A package that tries to make filesystem operations such as deleting subtrees
easier. It also creates an abstraction layer for i.e. snapshot management.
"""

from tslb import settings

# Some exceptions - They must be ontop to be importable by modules imported
# down this module (package).
class NoSuchSnapshot(Exception):
    def __init__(self, path, name):
        super().__init__("No such snapshot: `%s' of `%s'" % (name, path))

# Check settings
if 'Filesystem' not in settings:
    raise Exception('Filesystems section missing in TSLB config file.')

fstype = settings['Filesystem'].get('type')
if not fstype:
    raise Exception('Filesystem type not specified in TSLB config file.')

root = settings['Filesystem'].get('root')
if not root:
    raise Exception('No filesystem root specified in TSLB config file.')

# An abstract base for all filesystem implementations (currently there is only
# one - cephfs)
class Fsbase(object):
    def mount(self):
        """
        Mount the filesystem at the specified mountpoint (if applicable,
        otherwise do nothing).
        """
        pass

    def unmount(self):
        """
        Unmount the filesystem if applicable, otherwise do nothing.
        """
        pass

    def is_mounted(self):
        """
        :returns: True or False whether the fs is mounted or not.
        """
        return True

    def make_snapshot(self, path, name):
        raise NotImplementedError('make_snapshot')

    def delete_snapshot(self, path, name):
        raise NotImplementedError('delete_snapshot')

    def list_snapshots(self, path):
        raise NotImplementedError('list_snapshots')

    def restore_snapshot(self, path, name):
        raise NotImplementedError('restore_snapshot')


# Create a filesystem class of the specified type
if fstype == 'cephfs':
    monitor = settings['Filesystem'].get('monitor')
    if monitor is None:
        raise Exception('No ceph monitor specified in the TSLB config file.')

    subtree = settings['Filesystem'].get('subtree')
    if subtree is None:
        raise Exception('No cephfs subtree specified in the TSLB config file.')

    name = settings['Filesystem'].get('name')
    secret = settings['Filesystem'].get('secret')

    from .cephfs import cephfs
    fs = cephfs(monitor, subtree, root, name, secret)

else:
    raise Exception('Invalid filesystem type `%s\' specified in TSLB config file.' % fstype)

# Methods of the package being implemented by methods of modules' classes
def mount():
    """
    Mount the filesystem at the specified mountpoint (if applicable,
    otherwise do nothing).
    """
    fs.mount()

def unmount():
    """
    Unmount the filesystem if applicable, otherwise do nothing.
    """
    fs.unmount()
