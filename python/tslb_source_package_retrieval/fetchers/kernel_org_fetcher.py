"""
A fetcher for the Linux Kernel.
"""
import re
from bs4 import BeautifulSoup
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *


class KernelOrgFetcher(BaseFetcher):
    name = "kernel_org"

    def handles_url(session, package_name, url, out):
        return url == 'https://www.kernel.org'

    def fetch_versions(session, package_name, url, out, **kwargs):
        # Interpret URL
        url, params = parse_querystring(url)
        branch = params.get('branch', 'stable')

        # Download the main page
        page = download_url(session, url).content
        b = BeautifulSoup(page, 'html.parser')

        releases = b.find(id='releases')
        versions = []

        def _add_version(version_number, row):
            # Find download- and signature download urls
            d_url = row.find('a', text='tarball')['href']
            sig_url = row.find('a', text='pgp')['href']

            # Don't use cdn for signature
            sig_url = sig_url.replace('cdn.kernel.org', 'kernel.org')

            # Determine compression format
            m = re.match(r'.*\.(tar\..*)$', d_url)
            if not m or m[1] not in EXT_COMP_MAP:
                return

            versions.append((version_number, {EXT_COMP_MAP[m[1]]: (d_url, sig_url)}))


        for row in releases.find_all('tr'):
            cols = row.find_all('td')
            _type = cols[0].get_text().replace(':', '')
            version_str = cols[1].get_text()
            version = None

            if re.match(r'^[0-9]+(\.[0-9-]+)*$', version_str):
                version = VersionNumber(version_str)

            # Find version based on ?branch= parameter
            if branch in ('stable', 'longterm') and branch == _type and version:
                _add_version(version, row)

        return versions

