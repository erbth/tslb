"""
Common utilities that are used by all buid pipeline stages.
"""

import os
import tempfile
from tslb import parse_utils


class PreparedBuildCommand:
    """
    A context manager that detects if a given 'build command' is actually a
    script or a command. In the former case it generates an executable
    temporary file from it. Moreover it preprocesses the command / script by
    replacing variables with given keys-value pairs. It yields a list of
    strings that is suitable for passing it to `subprocess.run`. If the 'build
    command' is found to be a script, the list will only contain the absolute
    path to the script, otherwise the command and its arguments.

    If the 'build command' is a script and it will be executed in a chroot
    environment, the `chroot' parameter can be set to place the script in the
    chroot environment's /tmp directory. The yielded list will then contain an
    absolute path in the chroot environment.

    :param str build_command: The build command to prepare
    :param Dict(str, str) ctx: The list of key-value pairs to substitute
    :param str chroot: An optional path to a chroot environment
    :yields List(str): A list of program and arguments to run.
    """
    def __init__(self, build_command, ctx, chroot=None):
        self.build_command = build_command
        self.ctx = ctx
        self.chroot = chroot
        self.tmp_path = None

        # Preprocess
        for key, value in ctx.items():
            self.build_command = self.build_command.replace('$(' + key + ')', value)

        # Determine if it is a script
        self.is_script = len(self.build_command) >= 2 and self.build_command[0:2] == '#!'

        if not self.is_script:
            self.build_command = parse_utils.split_quotes(self.build_command.strip())


    def __enter__(self):
        if self.is_script:
            tmp_dir = os.path.join(self.chroot, 'tmp') if self.chroot else None

            fd, self.tmp_path = tempfile.mkstemp(dir=tmp_dir)

            try:
                os.write(fd, self.build_command.encode('UTF-8'))

            except:
                os.unlink(self.tmp_path)

            finally:
                os.close(fd)

            try:
                os.chmod(self.tmp_path, 0o555)

                if self.chroot:
                    return ['/tmp/' + self.tmp_path.rsplit('/', 1)[1]]
                else:
                    return self.tmp_path

            except:
                os.unlink(self.tmp_path)

        else:
            return self.build_command


    def __exit__(self, exc_type, exc_value, traceback):
        if self.is_script:
            os.unlink(self.tmp_path)


    def __str__(self):
        if self.is_script:
            return "script: " + parse_utils.stringify_escapes(self.build_command[0:70])
        else:
            return ' '.join(self.build_command)
