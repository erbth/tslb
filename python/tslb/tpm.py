import re
import subprocess
import sys
from tslb import CommonExceptions as ces
from tslb.VersionNumber import VersionNumber
from tslb import Architecture


class Tpm2_pack:
    """
    A simple wrapper that calls tpm_pack2.
    """
    def __init__(self, tpm2_pack='tpm2_pack'):
        self._tpm2_pack = tpm2_pack

    @property
    def tpm2_pack(self):
        return self._tpm2_pack


    def pack(self, directory, stdout=sys.stdout, stderr=sys.stderr):
        """
        Package the unpacked form in the given directory.

        :param str directory: The root of the unpacked form.
        :param stdout: sys.stdout-like object for tpm2_pack's stdout
        :param stderr: sys.stdout-like object for tpm2_pack's stderr
        :raises `CommonExceptions.CommandFailed`: If packaging fails.
        """
        cmd = [self._tpm2_pack, '.']

        res = subprocess.run(cmd, cwd=directory,
                stdout=stdout.fileno(), stderr=stderr.fileno())

        if (res.returncode != 0):
            raise ces.CommandFailed(' '.join(cmd))


class Tpm2:
    """
    A simple wrapper that calls TPM version 2.

    :param target: Path to the target system that should be modified. Defaults
        to a native target ('/').

    :param tpm2: Path to the tpm2 executable
    """
    def __init__(self, target=None, tpm2='tpm2'):
        self._tpm2 = tpm2
        self._target = target

    @property
    def tpm2(self):
        return self._tpm2

    @property
    def target(self):
        return self._target


    def install(self, pkgs):
        """
        Install a set of packages.

        :param pkg: An iterable of packages to install,
            like list(tuple(name, architecture, version)) or list(name,
            architecture), even mixed lists are allowed.

        :raises CommonExceptions.CommandFailed: if installing failes.
        """
        cmd = [self._tpm2, '--install', '--assume-yes', '--adopt-all']

        if self._target:
            cmd += ['--target', self._target]

        for e in pkgs:
            if len(e) == 2:
                n, a = e
                cmd.append("%s@%s" % (n, Architecture.to_str(a)))

            else:
                n, a, v = e
                cmd.append("%s@%s=%s" % (n, Architecture.to_str(a), v))

        if subprocess.run(cmd).returncode != 0:
            raise ces.CommandFailed(' '.join(cmd))


    def mark_auto(self, pkgs):
        """
        Set the given packages' installation reason to automatic.

        :param pkgs: An iterable of packages to mark, like list(tuple(name,
            architecture)).

        :raises CommonExceptions.CommandFailed: if the operation fails.
        """
        cmd = [self._tpm2, '--mark-auto']

        if self._target:
            cmd += ['--target', self._target]

        for n,a in pkgs:
            cmd.append("%s@%s" % (n, Architecture.to_str(a)))

        if subprocess.run(cmd).returncode != 0:
            raise ces.CommandFailed(' '.join(cmd))


    def list_installed_packages(self):
        """
        List the installed packages.

        :returns: list(tuple(name, architecture, version      ))
        :rtype:   List(Tuple(str , int         , VersionNumber))
        :raises CommonExceptions.CommandFailed: if the operation fails.
        """
        cmd = [self._tpm2, '--list-installed']

        if self._target:
            cmd += ['--target', self._target]

        res = subprocess.run(cmd, stdout=subprocess.PIPE)
        if res.returncode != 0:
            raise ces.CommandFailed(' '.join(cmd))

        pkg_list = []

        for line in res.stdout.split(b'\n'):
            if not line:
                continue

            m = re.match(r'^(\S+)\s+@\s+(\S+)\s+:\s+(\S+)\s+.*', line.decode('utf8'))
            pkg_list.append((
                m.group(1),
                Architecture.to_int(m.group(2)),
                    VersionNumber(m.group(3))
                ))

        return pkg_list


    def remove_unneeded(self):
        """
        Remove unneeded packages.

        :raises CommonExceptions.CommandFailed: if the operation fails.
        """
        cmd = [self._tpm2, '--remove-unneeded', '--assume-yes']

        if self._target:
            cmd += ['--target', self._target]

        if subprocess.run(cmd).returncode != 0:
            raise ces.CommandFailed(' '.join(cmd))
