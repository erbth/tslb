"""
Fetch SQLite versions...
"""
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *


class SQLiteFetcher(BaseFetcher):
    name = 'sqlite_fetcher'

    def handles_url(session, package_name, url, out):
        return url.startswith('https://sqlite.org/')

    def fetch_versions(session, package_name, url, out, **kwargs):
        # Download page
        page = download_url(session, url).content.decode('utf8')

        # Examine script-download-comment
        regex = re.compile(r'^PRODUCT,([^,]+),([^,]+/sqlite-autoconf-3[^,]+\.tar\.gz),[^,]+,([^,]+)$')
        for line in page.split('\n'):
            line = line.strip()
            m = regex.match(line)
            if m:
                v = VersionNumber(m[1])
                archive_url = urljoin(url, m[2])
                sha3 = m[3].lower()

                return [(v, {'gz': (archive_url, 'sha3:' + sha3)})]

        return []
