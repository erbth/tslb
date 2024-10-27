from . import Fsbase, NoSuchSnapshot
from tslb.CommonExceptions import CommandFailed, SavedYourLife
import os
import shutil
import stat
import subprocess

class cephfs(Fsbase):
    def __init__(self, monitor, fs_name, subtree, root, name,
                 secret=None, fsid=None):

        self.monitor = monitor
        self.fs_name = fs_name
        self.subtree = subtree
        self.root = root
        self.name = name
        self.secret = secret
        self.fsid = fsid
        self._dev_desc = '%s@%s.%s=%s' % (self.name, self.fsid, self.fs_name, self.subtree)

        # Format used in /proc/mounts by older kernels
        self._dev_desc_old = '%s:%s' % (self.monitor, self.subtree)


    def mount(self):
        if not self.is_mounted():
            cmd = [ 'mount', '-t', 'ceph',
                   self._dev_desc, self.root,
                   '-omon_addr=%s' % self.monitor.replace(',', '/') ]

            if self.secret is not None:
                cmd.append('-osecret=%s' % self.secret)

            if self.fsid is not None:
                cmd.append('-ofsid=%s' % self.fsid)

            ret = subprocess.call(cmd)
            if ret != 0:
                raise CommandFailed(' '.join(cmd), ret)

    def unmount(self):
        if self.is_mounted():
            cmd = [ 'umount', self.root ]

            ret = subprocess.call(cmd)
            if ret != 0:
                raise CommandFailed(' '.join(cmd), ret)

    def is_mounted(self):
        # Check if it is mounted (older kernels may use a different device
        # description format)
        cmds = [
                [ 'findmnt', self._dev_desc, self.root ],
                [ 'findmnt', self._dev_desc_old, self.root]
        ]

        for cmd in cmds:
            ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ret == 0:
                return True

        # If not, check if something else is mounted
        cmd = [ 'findmnt', self.root ]

        ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret == 0:
            raise SavedYourLife('Something else appears to be mounted on our root (`%s\').' %
                    self.root)

    def make_snapshot(self, path, name):
        if name[0] == '_':
            raise Exception("Snapshot names must not start with a _.")

        os.mkdir(os.path.join(path, '.snap', name))

    def delete_snapshot(self, path, name):
        os.rmdir(os.path.join(path, '.snap', name))

    def list_snapshots(self, path):
        return os.listdir(os.path.join(path, '.snap'))

    def restore_snapshot(self, path, name):
        if name not in self.list_snapshots(path):
            raise NoSuchSnapshot(path, name)

        # Delete all content in this directory
        def special_rm(p):
            if os.path.exists(p) and\
                    stat.S_ISDIR(os.stat(p, follow_symlinks=False).st_mode):
                for e in os.listdir(p):
                    # Commodity files
                    if e != '.' and e != '..':
                        special_rm (os.path.join(p, e))

                # Snapshots
                snapdir = os.path.join(p, '.snap')
                if os.path.exists(snapdir) and\
                        stat.S_ISDIR(os.stat(snapdir, follow_symlinks=False).st_mode):

                    for s in os.listdir(snapdir):
                        if s != '.' and s != '..' and s[0] != '_':
                            os.rmdir(os.path.join(snapdir, s))

                os.rmdir(p)
            else:
                os.unlink(p)

        for e in os.listdir(path):
            if e != '.' and e != '..':
                special_rm (os.path.join(path, e))

        # Copy content back
        snappath = os.path.join(path, '.snap', name)

        for e in os.listdir(snappath):
            if e != '.' and e != '..':
                src = os.path.join(snappath, e)
                dst = os.path.join(path, e)

                if os.path.exists(src) and\
                        stat.S_ISDIR(os.stat(src, follow_symlinks=False).st_mode):
                    shutil.copytree(src, dst, symlinks=True, ignore_dangling_symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)
