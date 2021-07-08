#!/usr/bin/python3
"""
For each enabled source package that has no upstream source url, try to guess
one.
"""
import argparse
import requests
from tslb import Architecture
from tslb import SourcePackage as spkg
from tslb.parse_utils import is_yes, query_user_input
from tslb.Console import Color


def main():
    parser = argparse.ArgumentParser("List enabled source packages without upstream url")
    parser.add_argument(metavar="<arch>", dest="arch", help="Architecture")
    args = parser.parse_args()
    arch = Architecture.to_int(args.arch)

    for name in spkg.SourcePackageList(arch).list_source_packages():
        sp = spkg.SourcePackage(name, arch)
        enabled = bool([True for v in sp.list_version_numbers()
            if is_yes(sp.get_version(v).get_attribute_or_default('enabled', None))])

        if not enabled or sp.has_attribute('upstream_source_url'):
            continue

        print("`%s':" % sp.short_str())

        urls = [
            'https://mirror.netcologne.de/gnu/%(pkg_name)s',
            'https://mirror.netcologne.de/savannah/%(pkg_name)s'
        ]

        success = False
        for url in urls:
            url = url % {
                'pkg_name': sp.name
            }

            print("    Trying url '%s'... " % url, end='', flush=True)
            try:
                resp = requests.get(url)
                if resp.status_code != 200:
                    raise HttpStatusError(resp.status_code)

            except (HttpStatusError, requests.RequestException) as e:
                print(Color.RED + "failed" + Color.NORMAL + " (%s)" % e)
                continue

            print(Color.GREEN + "OK" + Color.NORMAL)

            r = query_user_input("  Set this URL (d: try different url for this package)?", "ynd")
            if r == 'y':
                # Upgrade lock
                sp2 = spkg.SourcePackage(sp.name, sp.architecture, write_intent=True)
                sp = sp2

                sp.set_attribute('upstream_source_url', url)
                success = True
                break

            elif r == 'n':
                break

        if not success:
            print(Color.RED + "    No URL found." + Color.NORMAL)


#********************************** Exceptions ********************************
class HttpStatusError(Exception):
    def __init__(self, status_code):
        super().__init__("Unexpected HTTP status: %s" % status_code)


# Call entrypoint
if __name__ == '__main__':
    main()
    exit(0)
