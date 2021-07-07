"""
Finding version numbers of source packages given a 'source' of packages (e.g. a
mirror on the internet).
"""
from bs4 import BeautifulSoup
from tslb.VersionNumber import VersionNumber
from urllib.parse import urljoin
import re
import requests

def find_versions_at_url(package, url):
    """
    Finds version numbers of a package served at a given URL using different
    heuristics. The function tries different heuristics and if none is
    applicable raises an `UnknwonWebpageFormat` exception.

    :param str package: Name of the package to search for (e.g. 'binutils')
    :param str url:
    :returns: List((version number, (absolute url, absolute signature url)))
    :raises UnknownWebpageFormat: If the format of the web page could not be
        understood.
    :raises LoadError: If the page could not be loaded
    """
    # Fetch page
    try:
        resp = requests.get(url)
    except requests.exceptions.RequestsException as e:
        raise LoadError(url, str(e)) from e

    if resp.status_code < 200 or resp.status_code >= 300:
        raise LoadError(resp.url, "HTTP status: %s" % resp.status_code)

    page = resp.content

    # Interpret page
    ret = find_versions_at_url_list_a(package, resp.url, page)

    if ret is None:
        raise UnknownWebpageFormat(resp.url, "no heuristic applicable")

    # Choose compression format
    output = []
    for v, formats in ret:
        annotated = []
        for f, urls in formats.items():
            p = {
                'lz': 0,
                'zstd': 1,
                'gz': 2,
                'bz2': 3,
                'xz': 4
            }[f]
            annotated.append((p, urls))

        output.append((v, max(annotated)[1]))

    output.sort()
    return output

def find_versions_at_url_list_a(package, url, page):
    """
    Try to find package versions by interpreting the webpage as 'list' of links
    (extracting all links on the page).

    :param str package: Name of the package to search for
    :param str url: URL of the page (used for relative link targets)
    :param str page: Downloaded webpage
    :returns: List((version number, {compression format -> (absolute url, absolute signature url})),
        with <compression format> in (gz, bz2, xz, lz, zstd)
    """
    versions = {}
    signatures = {}
    b = BeautifulSoup(page, 'html.parser')

    regexs = [
        (re.compile(r"^" + re.escape(package) + r'-([.0-9a-zA-Z]+)\.((tar\.(gz|bz2|xz|lz|zstd))|tgz)(\.(sign|sig|asc))?$'), (1, 2, 6)),
        (re.compile(r"^" + re.escape(package) + r'-(([0-9]+\.)*[0-9a-zA-Z]+)\.(sign|sig|asc)$'), (1, None, 3))
    ]

    for a in b.find_all('a'):
        text = a.get_text()

        for (regex, pos) in regexs:
            pv, pc, psign = pos

            m = re.match(regex, text)
            if not m:
                continue

            try:
                v = VersionNumber(m[pv])
            except ValueError:
                continue

            if v not in versions:
                versions[v] = {}

            if pc:
                comp = {
                    'tgz': 'gz',
                    'tar.gz': 'gz',
                    'tar.bz2': 'bz2',
                    'tar.xz': 'xz',
                    'tar.lz': 'lz',
                    'tar.zstd': 'zstd'
                }[m[pc]]

                if psign and m[psign]:
                    signatures[(v, comp)] = urljoin(url, a['href'])
                else:
                    versions[v][comp] = urljoin(url, a['href'])

            elif psign and m[psign]:
                signatures[v] = urljoin(url, a['href'])

    # Add signature urls
    if not versions:
        return None

    composed = []
    for v, urls in versions.items():
        composed_urls = {}
        for comp, url in urls.items():
            sig_url = signatures.get((v, comp), signatures.get(v, None))
            composed_urls[comp] = (url, sig_url)

        composed.append((v, composed_urls))

    return composed


#****************************** Exceptions ************************************
class FindException(Exception):
    pass

class UnknownWebpageFormat(FindException):
    def __init__(self, url, msg):
        super().__init__("Invalid webpage format at '%s': %s" % (url, msg))
        self._url = url

    @property
    def url(self):
        return self._url

class LoadError(FindException):
    def __init__(self, url, msg):
        super().__init__("Failed to load '%s': %s" % (url, msg))
        self._url = url

    @property
    def url(self):
        return self._url
