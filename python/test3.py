#!/usr/bin/python3

from tslb.program_analysis import bash_parser, bash_tools
from tslb.basic_utils import read_file
import re


f = read_file('/usr/sbin/grub-mkconfig', 'system')

def include_loader(path):
    print("Load request: %s" % path)
    if re.match(r'^/[0-9a-zA-Z_./-]+$', path):
        print("  granted.")
        return read_file(path, 'system')
    return None

programs = bash_tools.determine_required_programs(f, include_loader)

print("\n\nRequired external programs:")
for p in sorted(programs):
    print("    %s" % p)
