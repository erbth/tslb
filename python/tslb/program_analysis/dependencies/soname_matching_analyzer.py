"""
Find dependencies by searching for the SONAME'd files of cdeps' shared
libraries in ELF files. This analyzer can therefore e.g. find libraries opened
with dlopen().
"""
import os
import stat
from tslb.SourcePackage import SourcePackage
from .dependency_analyzer import *


class SONAMEMatchingAnalyzer(BaseDependencyAnalyzer):
    """
    Find dependencies by searching for cdeps' SONAME'd files in ELF files.
    """
    name = 'soname_matching_analyzer'
    enabled_by_default = False

    @classmethod
    def analyze_root(cls, dirname, arch, out, spv=None, _cache=None):
        """
        :param _cache: cdep->shlibs cache; for internal use only
        """
        deps = set()
        _cache = {}

        def analyze(d):
            nonlocal deps

            for c in os.listdir(d):
                full_path = os.path.join(d, c)
                st_buf = os.lstat(full_path)

                if stat.S_ISDIR(st_buf.st_mode):
                    analyze(full_path)
                elif stat.S_ISREG(st_buf.st_mode):
                    deps |= cls.analyze_file(full_path, arch, out, spv, _cache)

        analyze(dirname)
        return deps


    @classmethod
    def analyze_file(cls, filename, arch, out, spv=None, _cache=None):
        # Is this an ELF file?
        st_buf = os.lstat(filename)
        if not stat.S_ISREG(st_buf.st_mode):
            return set()

        with open(filename, 'rb') as f:
            if f.read(4) != b'\x7fELF':
                return set()

            f.seek(0)
            return cls.analyze_buffer(f.read(), arch, out, spv, _cache)


    @classmethod
    def analyze_buffer(cls, buf, arch, out, spv=None, _cache=None):
        # Is this an ELF file?
        if buf[:4] != b'\x7fELF':
            return set()

        deps = set()

        # Find shared libraries of cdeps
        if not spv.has_attribute('cdeps'):
            return deps

        for f in cls._get_sos_for_spv(spv, _cache):
            if os.path.basename(f).encode('ascii') in buf:
                deps.add(FileDependency(f))

        return deps


    def _get_sos_for_spv(spv, cache):
        key = (spv.name, spv.version_number)
        if not cache or key not in cache: 
            so_files = []

            if spv.has_attribute('cdeps'):
                for cdep in spv.get_attribute('cdeps').get_required():
                    cdep_sp = SourcePackage(cdep, spv.architecture)
                    cdep_spv = cdep_sp.get_version(max(cdep_sp.list_version_numbers()))

                    for shlib in cdep_spv.get_shared_libraries():
                        so_files += list(shlib.get_abi_versioned_files())

            if cache:
                cache[key] = so_files

        else:
            so_files = cache[key]

        return so_files
