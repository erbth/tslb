"""
Finding version numbers of source packages given a 'source' of packages (e.g. a
mirror on the internet).
"""
from bs4 import BeautifulSoup
from tslb.VersionNumber import VersionNumber
from urllib.parse import urljoin
import os
import re
import requests
import subprocess
import sys
import tempfile

EXT_COMP_MAP = {
    'tgz': 'gz',
    'tar.gz': 'gz',
    'tar.bz2': 'bz2',
    'tar.xz': 'xz',
    'tar.lz': 'lz',
    'tar.zstd': 'zstd'
}

def find_versions_at_url(package, url, out=sys.stdout, verbose=False):
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
    ret = None

    # URL-base heuristics
    if url.startswith('https://github.com') and url.endswith('.git'):
        # Assume it's a github url.
        ret = find_versions_in_github_repo(package, url, out, verbose)

    else:
        # Plain page-based heuristics
        # Fetch page
        try:
            resp = requests.get(url)
        except requests.RequestException as e:
            raise LoadError(url, str(e)) from e

        if resp.status_code < 200 or resp.status_code >= 300:
            raise LoadError(resp.url, "HTTP status: %s" % resp.status_code)

        page = resp.content

        # Interpret page
        ret = find_versions_at_url_list_a(package, resp.url, page)

        if ret is None:
            raise UnknownWebpageFormat(resp.url, "no heuristic applicable")

    if ret is None:
        raise UnknownWebpageFormat(url, "no heuristic applicable")

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
                'xz': 4,
                'git': 5
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
        (re.compile(r"^" + re.escape(package) + r'-([.0-9]+[a-zA-Z]?)\.((tar\.(gz|bz2|xz|lz|zstd))|tgz)(\.(sign|sig|asc))?$'), (1, 2, 6)),
        (re.compile(r"^" + re.escape(package) + r'-(([0-9]+\.)*[0-9]+[a-zA-Z]?)\.tar\.(sign|sig|asc)$'), (1, None, 3))
    ]

    for a in b.find_all('a'):
        text = a.get_text().strip()
        href_file = a['href'].split('/')[-1]

        for (regex, pos) in regexs:
            pv, pc, psign = pos

            m = re.match(regex, text) or re.match(regex, href_file)
            if not m:
                continue

            try:
                v = VersionNumber(m[pv])
            except ValueError:
                continue

            if v not in versions:
                versions[v] = {}

            if pc:
                comp = EXT_COMP_MAP[m[pc]]

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


def _probe_url(url):
    cnt = 0

    while True:
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10)
            if resp.status_code == 404:
                return False
            elif resp.status_code == 200:
                return True
            else:
                raise LoadError(resp.url, "HTTP status: %s" % resp.status_code)

        except requests.RequestException as e:
            raise LoadError(release_url, str(e)) from e

        except requests.Timeout:
            cnt += 1
            if cnt >= 2:
                raise


def find_versions_in_github_repo(package, url, out=sys.stdout, verbose=False, only_n_newest=5):
    """
    Try to find packages on a github-releases page.

    :param str package: Name of the package to search for
    :param str url:
    :returns: List((version number, {compression format -> (absolute url, absolute signature url})),
        with <compression format> in (gz, bz2, xz, lz, zstd, git), git means
        the url refers to a git-repository (also indicated by the trailing
        '.git' in the url; the tag pointing to the version will be given as
        artifical querystring variable ?tag=<...>)
    :raises LoadError: If the page could not be loaded
    """
    versions = []

    # Get tags in repository
    ret = subprocess.run(['git', 'ls-remote', '--tags', url], stdout=subprocess.PIPE)
    if ret.returncode != 0:
        raise LoadError(url, "git ls-remote returned non-zero: %s" % ret.returncode)

    tags = []
    for line in ret.stdout.decode().split('\n'):
        line = line.strip()
        if not line:
            continue

        m = re.match(r'^\S+\s+refs/tags/(\S+)$', line)
        if not m:
            continue

        # Skip dereferenced tags
        if m[1].endswith('^{}'):
            continue

        tags.append(m[1])

    # Sort out tags that cannot be interpretted as version numbers and sort
    # tags in descending order.
    annotated_tags = []
    for tag in tags:
        # Skip release candidates
        if 'rc' in tag.lower():
            continue

        v_str = None

        m = re.match(r'^v?([0-9]+(\.[0-9a-zA-Z.]+)?)$', tag)
        if m:
            v_str = m[1]

        # Used by expat
        m = re.match(r'^R_([0-9]+(_[0-9]+)*)$', tag)
        if m:
            v_str = m[1].replace('_', '.')

        # Try to exclude timestamps
        if v_str and re.match(r'.*[0-9]{5,}.*', v_str):
            v_str = None

        if v_str is not None:
            annotated_tags.append((VersionNumber(v_str), v_str, tag))

    annotated_tags.sort()
    annotated_tags.reverse()

    # Find GitHub Releases for tags; only consider n newest releases
    # releases is a list [(release tag name, version, release url)]
    releases = []
    for i, t in enumerate(annotated_tags):
        v, v_str, tag = t

        if only_n_newest and i >= only_n_newest:
            break

        release_url = url.replace('.git', '/releases/' + tag)

        if verbose:
            print("  Probing '%s' ..." % release_url, file=out)

        if _probe_url(release_url):
            releases.append((tag, v, v_str, release_url))

    if not releases:
        return None


    # Case 1: conventional autotools source packages uploaded as assets.
    latest_sig_found = False
    first = True

    for tag, v, v_str, release_url in releases:
        # Probe a few filenames
        found = False
        for ext in ['tar.xz', 'tar.bz2', 'tar.gz', 'tgz', 'tar.lz', 'tar.zstd']:
            download_url = url.replace('.git', '/releases/download/%s/%s-%s.%s' %
                    (tag, package, v_str, ext))

            if verbose:
                print("  Probing '%s' ..." % download_url)

            if _probe_url(download_url):
                found = True

                # Try to find signature
                sig_found = False
                for sig_ext in ['sig', 'sign', 'asc']:
                    signature_download_url = download_url + '.' + sig_ext

                    print("  Probing '%s' ..." % signature_download_url)
                    if _probe_url(signature_download_url):
                        sig_found = True
                        if first:
                            latest_sig_found = True

                        break

                versions.append((v, {
                    EXT_COMP_MAP[ext]: (download_url, signature_download_url if sig_found else None)
                }))

            if found:
                break

        first = False

    # If the latest version did not have a signature, try to find a signed
    # commit as well.
    if versions and latest_sig_found:
        return versions


    # Case 2: signed commits
    commit_versions = []
    commit_version_signed = False

    # Clone repository
    with tempfile.TemporaryDirectory() as tmpdir:
        ret = subprocess.run(['git', 'clone', '--bare', url], cwd=tmpdir)
        if ret.returncode != 0:
            raise LoadError(url, "git clone --bare failed with code %s." % ret.returncode)

        repo_dir = os.path.join(tmpdir, os.listdir(tmpdir)[0])

        for tag, v, v_str, release_url in releases:
            # Check if tag or commit of tag is signed, and if yes, add the
            # release as version.
            cmd = ['git', 'show', '--stat', '--pretty=%GG', tag]
            ret = subprocess.run(
                    cmd,
                    cwd=repo_dir,
                    stdout=subprocess.PIPE)

            if ret.returncode != 0:
                raise LoadError(url, ' '.join(cmd) + " failed with code %s." % ret.returncode)

            text = ret.stdout.decode()
            if 'BEGIN PGP SIGNATURE' in text or text.startswith('gpg'):
                commit_version_signed = True

            commit_versions.append((v, {'git': (url + "?tag=" + tag, None)}))

    if commit_version_signed:
        return commit_versions
    elif versions:
        return versions
    elif commit_versions:
        return commit_versions
    else:
        return None


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
