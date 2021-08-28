#!/usr/bin/python3
"""
List (reverse) dependencies between source packages.

Considers the latest enabled version only or the latest version, if no version
is enabled. Missing dependencies are ignored and a warning is printed.

There's also an all-versions mode that considers all versions of the given
source package and other source packages.
"""
import argparse
from tslb import Architecture
from tslb import parse_utils
from tslb.Console import Color
from tslb.Constraint import DependencyList
from tslb.SourcePackage import SourcePackageList, SourcePackage


def parse_args():
    """
    Parse arguments
    """
    parser = argparse.ArgumentParser("List source dependencies")
    parser.add_argument('-a', "--arch", help="Architecture (%s)" %
                '|'.join(Architecture.architectures_reverse),
            nargs=1, required=True)

    parser.add_argument('-r', '--reverse', action='store_true', help="Reverse dependencies")
    parser.add_argument('pkg', metavar="<pkg>",
            help="The package the dependencies of which to explore")

    parser.add_argument("--all-versions", action='store_true', help="Consider all versions")

    args = parser.parse_args()

    try:
        args.arch = Architecture.to_int(args.arch[0])
    except (ValueError, KeyError):
        print("Invalid architecture.")
        exit(1)

    return args


def build_cdep_graph(args):
    """
    Build the cdep graph using the given parameters. The graph (and transposed
    graph) is represented as adjacency list.

    Note that the package base is not locked ...

    :returns: (G, GT (transposed))
    """
    G = {}
    GT = {}

    versions = []
    sp = None
    spv = None
    chosen_spv = None

    for name in SourcePackageList(args.arch).list_source_packages():
        sp = SourcePackage(name, args.arch)
        chosen_spv = None

        vs = sp.list_version_numbers()
        for v in reversed(sorted(vs)):
            spv = sp.get_version(v)
            if parse_utils.is_yes(spv.get_attribute_or_default('enabled', 'false')):
                chosen_spv = spv
                break

        if not chosen_spv and vs:
            chosen_spv = sp.get_version(max(vs))

        if not chosen_spv:
            continue

        versions.append(chosen_spv)


    del chosen_spv
    del spv
    del sp

    # Add dependencies
    G = {v.source_package.name: set() for v in versions}

    for spv in versions:
        v = spv.source_package.name
        for u in spv.get_attribute_or_default('cdeps', DependencyList()).get_required():
            if u not in G:
                print(Color.BRIGHT_YELLOW + "WARNING: `%s' depends on non-existent `%s' (ignored)." %
                        (v, u) + Color.NORMAL)

            G[v].add(u)


    # Build the transposed graph
    GT = {k: set() for k in G}
    for v, us in G.items():
        for u in us:
            if u in GT:
                GT[u].add(v)

    return G, GT


def main():
    args = parse_args()

    if not args.all_versions:
        # 'Graph mode'
        G, GT = build_cdep_graph(args)

        if args.pkg not in G:
            print("The requested package is not in the cdep graph.")
            exit(1)

        g = GT if args.reverse else G
        for u in sorted(g[args.pkg]):
            print(u)

        return


    # 'All versions mode'
    sp_names = SourcePackageList(args.arch).list_source_packages()
    if args.pkg not in sp_names:
        print("The requested package does not exist.")

    if args.reverse:
        output = []

        v_sp = SourcePackage(args.pkg, args.arch)
        vs = [v_sp.get_version(v_v) for v_v in v_sp.list_version_numbers()]

        for u in sp_names:
            sp_u = SourcePackage(u, args.arch)
            for u_v in sp_u.list_version_numbers():
                u_spv = sp_u.get_version(u_v)

                u_cdeps = u_spv.get_attribute_or_default('cdeps', DependencyList())
                if args.pkg not in u_cdeps.get_required():
                    continue

                for v_spv in vs:
                    if (v_spv.source_package.name, v_spv.version_number) in u_cdeps:
                        output.append((u_spv, v_spv))

        output.sort(key=lambda t: (t[1].version_number, t[0].version_number))
        output.reverse()

        for u, v in output:
            print("`%s' -> `%s'" % (u, v))

    else:
        v_sp = SourcePackage(args.pkg, args.arch)
        for v_v in reversed(v_sp.list_version_numbers()):
            v_spv = v_sp.get_version(v_v)

            v_cdeps = v_spv.get_attribute_or_default('cdeps', DependencyList())
            for u in v_cdeps.get_required():
                if u not in sp_names:
                    print(Color.BRIGHT_YELLOW + "WARNING: `%s' depends on non-existent `%s' (ignored)." %
                            (v_spv, u) + Color.NORMAL)
                    continue

                u_sp = SourcePackage(u, args.arch)
                for v_u in reversed(u_sp.list_version_numbers()):
                    if (u_sp, v_u) not in v_cdeps:
                        continue

                    u_spv = u_sp.get_version(v_u)
                    print("`%s' -> `%s'" % (v_spv, u_spv))


if __name__ == '__main__':
    main()
    exit(0)
