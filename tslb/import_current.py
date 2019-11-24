#!/usr/bin/python3
import os
import stat
import re
import Console

from VersionNumber import VersionNumber
from Constraint import VersionConstraint, DependencyList
from Architecture import amd64
from SourcePackage import SourcePackageList, SourcePackage, SourcePackageVersion

current_base = '/home/therb/projects/TSClientLEGACY/.old/tslegacy/packaging'
ignored_dirs = set([
    'skel',
    'xorg-applications-all',
    'xorg-libraries',
    'xorg-libraries-dev',
    'xorg-fonts'
    ])

class old_sp(object):
    def __init__(self, name, directory, version_number):
        version_number = VersionNumber(version_number)

        self.name = name
        self.directory = directory
        self.description_mk = os.path.join(self.directory, 'description.mk')
        self.version_number = version_number
        self.source_archive = None
        self.unpacked_source_directory = None
        self.cdeps = None

def expand_make_variables(variables, text):
    """
    Does one round of variable expansion.

    :param variables: dict name -> value
    :param text: The text in which variables should be expanded.
    """
    open_brackets = 0
    start_position = -1
    start_open_brackets = -1

    third_last_char = None
    second_last_char = None
    last_char = None

    text_len = len(text)
    i = 0

    while i < text_len:
        c = text[i]

        if c == '(':
            open_brackets += 1
        if c == ')':
            open_brackets -= 1

        if c != '(' and last_char == '$' and second_last_char != '$':
            # Single-letter variable
            if c in variables:
                text = text[:i-1] + variables[c] + text[i+1:]
                text_len = len(text)
                i += len(variables[c])

                third_last_char = None
                second_last_char = None
                last_char = None

            else:
                i += 1
                third_last_char = second_last_char
                second_last_char = last_char
                last_char = c

        elif c == '(' and last_char == '$' and second_last_char != '$':
            # Begin of a multi-letter variable
            start_position = i - 1
            start_open_brackets = open_brackets

            i += 1
            third_last_char = second_last_char
            second_last_char = last_char
            last_char = c

        elif c == ')' and start_position >= 0 and start_open_brackets - 1 == open_brackets:
            # End of multi-letter variable
            variable_name = text[start_position+2:i]

            if variable_name in variables:
                text = text[:start_position] + variables[variable_name] + text[i+1:]
                text_len = len(text)
                i = start_position + len(variables[variable_name])

                third_last_char = None
                second_last_char = None
                last_char = None

            else:
                i += 1
                third_last_char = second_last_char
                second_last_char = last_char
                last_char = c

            start_position = -1
            start_open_brackets = -1

        else:
            i += 1
            third_last_char = second_last_char
            second_last_char = last_char
            last_char = c

    return text

def ParseDescription(d):
    """
    :param d: The subdirectory of base which contains the description.mk to
        parse.
    :returns: A new old_sp.
    """
    fpath = os.path.join(current_base, d)
    dpath = os.path.join(fpath, 'description.mk')

    name = d

    with open(dpath, 'r') as dfile:
        dcontent = dfile.readlines()

    # Parse the file line by line
    # Resolve line continuations
    odcontent = dcontent
    dcontent = []

    buf = None
    lc_regex = re.compile('(^.*)\\\s*$')

    for l in odcontent:
        m = re.match(lc_regex, l)

        if buf is None:
            if m:
                buf = m.group(1)
            else:
                dcontent.append(l)

        else:
            if m:
                buf += ' ' + m.group(1)
            else:
                dcontent.append(buf + ' ' + l)
                buf = None

    # Read and expand variables
    while True:
        make_variables = {}

        variable_regex = re.compile('^\s*((export)\s*)?([^ \t]+)\s*[:]?=\s*(.*)\s*$')
        for l in dcontent:
            m = re.match(variable_regex, l)
            if m:
                key = m.group(3)
                value = m.group(4)
                make_variables[key] = value

        odcontent = dcontent
        dcontent = []

        expand_regex = re.compile('\$\(([^\)]+)\)')
        for l in odcontent:
            l = expand_make_variables(make_variables, l)
            dcontent.append(l)

        if odcontent == dcontent:
            break

    # Interpret variables
    version_number = make_variables.get('%s_SRC_VERSION' % name, None)
    unpacked_source_directory = make_variables.get('%s_SRC_DIR' % name, None)
    source_archive = make_variables.get('%s_SRC_ARCHIVE' % name, None)

    if version_number is None:
        raise Exception('%s: version missing.' % name)
    elif source_archive is None:
        raise Exception('%s: archive missing.' % name)

    # Interpret compiletime dependencies
    cdeps_text = make_variables.get('%s_SRC_CDEPS' % name, None)
    if cdeps_text is None:
        raise Exception('%s: cdeps missing.' % name)

    cdeps = DependencyList()
    cdeps_list = cdeps_text.split()

    cdep_regex = re.compile('^(.+)_installed$')
    for cdep in cdeps_list:
        m = re.match(cdep_regex, cdep)
        if m:
            cdep = re.sub('-dev$', '', m.group(1))

            if cdep not in ignored_dirs:
                cdeps.add_constraint(VersionConstraint('', '0'), cdep)

    osp = old_sp(name, fpath, version_number)
    osp.source_archive = source_archive
    osp.cdeps = cdeps
    osp.unpacked_source_directory = unpacked_source_directory
    return osp

def main():
    # Find description.mk files and thus source packages.
    old_sps = list()

    for d in os.listdir(current_base):
        fpath = os.path.join(current_base, d)

        if stat.S_ISDIR(os.stat(fpath).st_mode) and d not in ignored_dirs:
            if os.path.exists(os.path.join(fpath, 'description.mk')):
                osp = ParseDescription(d)
                old_sps.append(osp)

    old_sps.sort(key=lambda x: x.name)

    spl = SourcePackageList(amd64)

    # Actually import the packages
    for osp in old_sps:
        Console.print_status_box('Importing source package `%s\'' % osp.name)

        sp = spl.create_source_package(osp.name)
        spv = sp.add_version(osp.version_number)

        spv.set_cdeps(osp.cdeps)
        spv.set_attribute('source_archive', osp.source_archive)
        spv.set_attribute('unpacked_source_directory', osp.unpacked_source_directory)

        del spv
        del sp

        Console.update_status_box(True)
    return 0

if __name__ == "__main__":
    exit(main())
