"""
Fetch versions from lists of links - 'directories' served via http(s).
"""
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *


class LinkListFetcher(BaseFetcher):
    name = 'link_list'

    def handles_url(session, package_name, url, out):
        return True

    def fetch_versions(session, package_name, url, out, **kwargs):
        versions = {}
        signatures = {}
        page = download_url(session, url).content
        b = BeautifulSoup(page, 'html.parser')

        regexs = [
            (re.compile(r"^" + re.escape(package_name) + r'-([.0-9]+[a-zA-Z]?)\.((tar\.(gz|bz2|xz|lz|zstd))|tgz)(\.(sign|sig|asc))?$'), (1, 2, 6)),
            (re.compile(r"^" + re.escape(package_name) + r'-(([0-9]+\.)*[0-9]+[a-zA-Z]?)\.tar\.(sign|sig|asc)$'), (1, None, 3))
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
            return []

        composed = []
        for v, urls in versions.items():
            composed_urls = {}
            for comp, url in urls.items():
                sig_url = signatures.get((v, comp), signatures.get(v, None))
                composed_urls[comp] = (url, sig_url)

            composed.append((v, composed_urls))

        return composed
