from . import Fsbase
from CommonExceptions import CommandFailed, SavedYourLife
import os
import subprocess

class cephfs(Fsbase):
    def __init__(self, monitor, subtree, root, name=None, secret=None):
        self.monitor = monitor
        self.subtree = subtree
        self.root = root
        self.name = name
        self.secret = secret

    def mount(self):
        if not self.is_mounted():
            cmd = [ 'mount', '-t', 'ceph', self.monitor + ':' + self.subtree,
                self.root ]

            if self.name is not None:
                cmd.append('-oname=%s' % self.name)

            if self.secret is not None:
                cmd.append('-osecret=%s' % self.name)

            ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ret != 0:
                raise CommandFailed(' '.join(cmd), ret)

    def unmount(self):
        cmd = [ 'umount', self.root ]

        ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret != 0:
            raise CommandFailed(' '.join(cmd), ret)

    def is_mounted(self):
        # Check if it is mounted
        cmd = [ 'findmnt', self.monitor + ':' + self.subtree, self.root ]

        ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret == 0:
            return True

        # If not, check if something else is mounted
        cmd = [ 'findmnt', '--target', self.root ]

        ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret == 0:
            raise SavedYourLife('Something else appears to be mounted on out root (`%s\').' %
                    self.root)

    def make_snapshot(self, path, name):
        os.mkdir(os.path.join(self.root, path, '.snap', name))

    def delete_snapshot(self, path, name):
        os.rmdir(os.path.join(self.root, path, '.snap', name))

    def list_snapshots(self, path):
        return os.listdir(os.path.join(self.root, path))

    def restore_snapshot(self, path, name):
        raise NotImplementedError('restore_snapshot')
