import re
import requests


class BaseFetcher:
    """
    Abstract base class for version fetchers
    """
    name = ''

    def handles_url(session, package_name, url, out):
        """
        :param session: HTTP requests session to use for requests (with
            potential caching)
        :param package_name: Name of the package to fetch
        :param url: URL from which to fetch the package
        :param out: sys.stdout-like object for printing information
        :returns: True if the URL can be handles by this fetcher
        :rtype: bool
        """
        raise NotImplementedError

    def fetch_versions(session, pacakge_name, url, out, **kwargs):
        """
        **kwargs: additional fetcher-specific parameters can be given here.

        :param session: HTTP requests session to use for requests (with
            potential caching)
        :param package_name: Name of the package to fetch
        :param url: URL from which to fetch the package
        :param out: sys.stdout-like object for printing information
        :returns: [(<version number>, {<type>: (download url, signature url)})]
            with `type' being one of 'lz', 'zstd', 'gz', 'bz2', 'xz', 'zip' and
            'git'. 'git' has an artificial querystring parameter `?tag=...' in
            the download url which specifies the tag to checkout.
        :raises UnknownWebpageFormat: If the format of the web page could not be
            understood.
        """
        raise NotImplementedError


def download_url(session, url, required=True, head=False):
    cnt = 0

    while True:
        try:
            if head:
                resp = session.head(url, allow_redirects=True, timeout=10)
            else:
                resp = session.get(url, timeout=10)

            if resp.status_code == 404 and not required:
                return None
            elif resp.status_code == 200:
                return resp
            else:
                raise LoadError(resp.url, "HTTP status: %s" % resp.status_code)

        except requests.RequestException as e:
            raise LoadError(url, str(e)) from e

        except requests.Timeout:
            cnt += 1
            if cnt >= 2:
                raise

def probe_url(session, url):
    return download_url(session, url, required=False, head=True)

# File extension to compression algorithm map
EXT_COMP_MAP = {
    'tgz': 'gz',
    'tar.gz': 'gz',
    'tar.bz2': 'bz2',
    'tar.xz': 'xz',
    'tar.lz': 'lz',
    'tar.zstd': 'zstd',
    'zip': 'zip'
}


# Utility functions for parsing urls
def parse_querystring(url):
    """
    url with querystring -> url without qs, {qs attributes}

    :raises ValueError: If the querystring cannot be understood
    """
    qs = {}

    m = re.match(r'^([^?]*)(\?(.*))?$', url)
    if m[2]:
        for param in m[3].split('&'):
            comp = param.split('=')
            if len(comp) != 2:
                raise ValueError("invalid querystring")

            qs[comp[0]] = comp[1].strip().strip("'").strip('"')

    return (m[1], qs)


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
