from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.parse_utils import is_yes


ARCH = 'amd64'

PREFIXES = ['/bin/', '/sbin/', '/lib/', '/lib32/', '/lib64/']

def main():
    pkgs = set()

    spl = SourcePackageList(ARCH)
    for n in spl.list_source_packages():
        sp = SourcePackage(n, ARCH)

        for v in sp.list_version_numbers():
            spv = sp.get_version(v)
            if not is_yes(spv.get_attribute_or_default('enabled', 'false')):
                continue

            for n in spv.list_current_binary_packages():
                bp = spv.get_binary_package(
                        n, max(spv.list_binary_package_version_numbers(n)))

                for f,_ in bp.get_files():
                    for pref in PREFIXES:
                        if f.startswith(pref):
                            pkgs.add((spv.name, spv.version_number))


    for n,v in pkgs:
        print("%s:%s" % (n,v))


if __name__ == '__main__':
    main()
    exit(0)
