"""
Finding version numbers of source packages given a 'source' of packages (e.g. a
mirror on the internet).
"""
import requests_cache
import sys
from . import fetchers
from .fetchers import FindException


CACHE_PATH = '/tmp/tslb_source_package_retrieval/cache.sqlite'


def find_versions_at_url(package, url, out=sys.stdout, verbose=False,
        cache_path=CACHE_PATH):
    """
    Finds version numbers of a package served at a given URL using heuristics.
    The function tries different heuristics and if none is applicable raises an
    `UnknownWebpageFormat` exception.

    :param str package: Name of the package to search for (e.g. 'binutils')
    :param str url:
    :returns: List((version number, (absolute url, absolute signature url)))
    :raises UnknownWebpageFormat: If the format of the web page could not be
        understood.
    :raises LoadError: If the page could not be loaded
    """
    versions = []

    session = requests_cache.CachedSession(cache_path)

    # Try different fetchers, which implement the heuristics
    for fetcher in fetchers.ALL_FETCHERS:
        if fetcher.handles_url(session, package, url, out):
            versions = fetcher.fetch_versions(session, package, url, out, verbose=verbose)
            break


    # Choose compression format
    output = []
    for v, formats in versions:
        annotated = []
        for f, urls in formats.items():
            p = {
                'zip': 0,
                'lz': 1,
                'zstd': 2,
                'gz': 3,
                'bz2': 4,
                'xz': 5,
                'git': 6
            }[f]
            annotated.append((p, urls))

        output.append((v, max(annotated)[1]))

    output.sort()
    return output
