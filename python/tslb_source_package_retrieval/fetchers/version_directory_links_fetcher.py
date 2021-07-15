"""
Fetch versions from lists of links that point to 'directories' containing
package versions; served via http(s).
"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *
from .link_list_fetcher import LinkListFetcher


class VersionDirectoryLinksFetcher(BaseFetcher):
    name = "version_directory_links"


    @classmethod
    def handles_url(cls, session, package_name, url, out):
        # Search for directories
        dirs = cls._find_version_directories(session, package_name, url, out)
        return len(dirs) > 0


    @classmethod
    def fetch_versions(cls, session, package_name, url, out, **kwargs):
        versions = []
        dirs = cls._find_version_directories(session, package_name, url, out)
        for d in dirs:
            # Fetch versions in the directory using LinkListFetcher
            _, url_params = parse_querystring(url)
            params = {}

            if 'link_target_format' in url_params:
                params['link_target_format'] = url_params['link_target_format']

            versions += LinkListFetcher.fetch_versions(
                    session, package_name, d, out, **params)

        return versions


    def _find_version_directories(session, package_name, url, out):
        # Interpret URL
        url, params = parse_querystring(url)

        directory_format = params.get('directory_format', r'v?[0-9]+(\.[0-9]+)*[a-zA-Z]?/?')
        regex = re.compile(directory_format, flags=re.I)

        link_target_format = params.get('link_target_format',
                re.escape(package_name) + r'.*\.(tgz|tar\.(gz|bz2|xz|lz|zstd)|zip)')

        archive_regex = re.compile(link_target_format, flags=re.I)

        dirs = []

        page = download_url(session, url).content
        b = BeautifulSoup(page, 'html.parser')

        for a in b.find_all('a'):
            text = a.get_text().strip()
            if regex.fullmatch(text):
                if not a.get('href'):
                    continue

                d = urljoin(url + '/', a['href'])

                # If the target does not have content type text/html, skip it
                # (might not be a directory listing then).
                resp = download_url(session, d, head=True)
                if not resp.headers['content-type'].strip().startswith('text/html'):
                    continue

                # Check if the directory contains an archive of the package
                dir_page = download_url(session, d).content
                dir_b = BeautifulSoup(dir_page, 'html.parser')

                for dir_a in dir_b.find_all('a'):
                    if not dir_a.get('href'):
                        continue

                    a_text = dir_a.get_text().strip()
                    a_href_filename = dir_a['href'].split('/')[-1].strip()

                    if re.match(archive_regex, a_text) or \
                            archive_regex.fullmatch(a_href_filename):
                        dirs.append(d)
                        break

        return dirs
