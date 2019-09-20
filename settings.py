"""
A settings wrapper presenting various system settings from a ini file in one of
the following locations:
  * ./tslb_system.ini
  * ~/.tslb_system.ini
  * /etc/tslb/system.ini
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
    def __init__(self):
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

    except:
        raise CannotReadConfigFile

# Executed on import
find_config_file()
parse_config_file()

# See e.g. http://sohliloquies.blogspot.com/2017/07/how-to-make-subscriptable-module-in.html
class settings_internal(types.ModuleType):
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

sys.modules[__name__] = settings_internal(__name__)
