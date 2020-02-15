"""
A settings wrapper presenting various system settings from a ini file in one of
the following locations:
  * ./tslb_system.ini
  * ~/.tslb_system.ini
  * /etc/tslb/system.ini

In addition to reading the config file and presenting it through a dict-like
interface, this module does also interpret the settings if desired, and create
ready-to-use config parameters for certain procedures (i.e. like ceph
environment variables).
Methods that interpret settings have the advantage of throwing an exception if
the required settings are not defined. That may be easier to use than looking up
the values by hand.
"""

import os
import types
import sys
import configparser

# Exceptions
class NoConfigFile(Exception):
    """
    To be raised when no system config file was found.
    """
    def __init__(self):
        super().__init__('No system config file found.')

class CannotReadConfigFile(Exception):
    """
    To be raised when reading the config file does not work.
    """
    def __init__(self, attr = None):
        if attr is not None:
            super().__init__('Cannot read the config file %s: %s' % (config_file_path, repr(attr)))
        else:
            super().__init__('Cannot read the config file %s.' % config_file_path)

# Some globals
config_file_path = None
options = {}

# Functions
def find_config_file():
    global config_file_path

    if os.path.exists('tslb_system.ini'):
        config_file_path = os.path.abspath('tslb_system.ini')
    elif os.path.exists(os.path.join(os.getenv('HOME'), '.tslb_system.ini')):
        config_file_path = os.path.join(os.getenv('HOME'), '.tslb_system.ini')
    elif os.path.exists('/etc/tslb/system.ini'):
        config_file_path = '/etc/tslb/system.ini'
    else:
        raise NoConfigFile

def parse_config_file():
    config = configparser.ConfigParser()

    try:
        config.read(config_file_path)

        for s in config:
            options[s] = {}

            for k in config[s]:
                options[s][k] = config[s][k]

    except Exception as e:
        raise CannotReadConfigFile(e)
    except:
        raise CannotReadConfigFile

# Executed on import
find_config_file()
parse_config_file()

# See e.g. http://sohliloquies.blogspot.com/2017/07/how-to-make-subscriptable-module-in.html
class settings_internal(types.ModuleType):
    """
    The actual settings module. The one read from this file will be replaced by
    an instance of this class during loading, see at the end of the file.
    """
    def __getitem__(self, key):
        if key == 'config_file_path':
            return config_file_path

        return options[key]

    def __contains__(self, key):
        if key == 'config_file_path':
            return True

        return key in options

    def get(self, key):
        if key == 'config_file_path':
            return config_file_path

        return options.get(key)


    # Interpret settings and formulate strings.
    def get_ceph_cmd_conn_params(self):
        """
        :returns: Like -m <monitors> --name <name> --keyring <keyringfile> as
            tuple for use with i.e. subprocess.run.
        """
        c = self.get('Ceph')
        if not c:
            raise NoSuchSetting('Ceph')

        monitor = c.get('monitor')
        if not monitor:
            raise NoSuchSetting('Ceph', 'monitor')

        name = c.get('name')
        if not name:
            raise NoSuchSetting('Ceph', 'name')

        keyring = c.get('keyring', '/etc/tslb/ceph.%s.keyring' % name)
        if not os.path.isfile(keyring):
            raise NoSuchFile('Ceph keyring for %s (file %s)' % (name, keyring))

        return ("-m", monitor, "--name", name, "--keyring", keyring)


    def get_ceph_rootfs_rbd_pool(self):
        """
        :raises NoSuchSetting: if required settings are missing.
        """
        try:
            return self['Ceph']['rootfs_rbd_pool']
        except KeyError:
            raise NoSuchSetting('Ceph', 'rootfs_rbd_pool')

    def get_temp_location(self):
        """
        Gets the configured or default temporary file location for tslb.
        """
        l = '/tmp/tslb'

        t = self.get('TSLB')
        if t:
            l = t.get('temp_location', l)

        return l


# **************************** Exceptions *************************************
class SettingsException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NoSuchSetting(SettingsException):
    def __init__(self, group, param=None):
        if param:
            super().__init__(f"{group}.{param} is not configured in system config file.")
        else:
            super().__init__(f"{group} is not defined in the system config file.")


class NoSuchFile(SettingsException):
    def __init__(self, msg):
        super().__init__("No such file: %s" % msg)


# Replace the file-sourced module by an instance of a class to allow control
# over __getitem__ etc.
sys.modules[__name__] = settings_internal(__name__)
