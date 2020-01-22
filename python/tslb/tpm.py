import subprocess
import Exceptions as es

class tpm(object):
    """
    A simple wrapper that calls the TPM.
    """

    PKG_TYPE_SW = 'sw'
    PKG_TYPE_CONF = 'conf'

    def __init__(self, tpm = 'tpm'):
        super().__init__
        self.tpm = tpm

    def create_desc (self, pkg_type):
        cmd = [self.tpm, '--create-desc', pkg_type]

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def set_name(self, name):
        cmd = [self.tpm, '--set-name', name]

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def set_version(self, version):
        cmd = [self.tpm, '--set-version', version]

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def set_arch(self, arch):
        cmd = [self.tpm, '--set-arch', arch]

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def remove_dependencies(self):
        cmd = [self.tpm, '--remove-dependencies']

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def add_dependencies(self, deps):
        for dep in deps:
            self.add_dependency(dep)

    def add_dependency(self, dep):
        cmd = [self.tpm, '--add-dependency', dep]
        print (' '.join(cmd))

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def add_files(self):
        cmd = [self.tpm, '--add-files']

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))

    def pack(self):
        cmd = [self.tpm, '--pack']

        if subprocess.call(cmd) != 0:
            raise es.CommandFailed(' '.join(cmd))
