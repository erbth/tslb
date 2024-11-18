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
        # Interpret URL
        url, params = parse_querystring(url)

        link_target_filter = params.get('link_target_filter')
        if link_target_filter:
            link_target_filter = re.compile(link_target_filter)

        link_target_format = kwargs.pop('link_target_format', params.get('link_target_format'))
        if link_target_format:
            link_target_format = re.compile(link_target_format)

        versions = {}
        signatures = {}
        page = download_url(session, url).content
        b = BeautifulSoup(page, 'html.parser')

        if link_target_format:
            regexs = [(link_target_format, (1,2,3))]

        else:
            regexs = [
                (re.compile(r"^" + re.escape(package_name) +
                        r'-?([.0-9]+[a-zA-Z]?[0-9]?)\.((tar\.(gz|bz2|xz|lz|zstd))|tgz|zip)(\.(sign|sig|asc))?$',
                        flags=re.I),
                    (1, 2, 6)
                ),

                (re.compile(r"^" + re.escape(package_name) +
                        r'-?(([0-9]+\.)*[0-9]+[a-zA-Z]?[0-9]?)\.tar\.(sign|sig|asc)$',
                        flags=re.I),
                    (1, None, 3)
                )
            ]

        # Try to find base url
        head = b.find('head')
        base_url = re.sub(r'/[^/]+\.html', '', url) + '/'
        if base_tag:=head.find('base'):
            if base_tag_href:=base_tag.get('href'):
                base_url = base_tag_href

        for a in b.find_all('a'):
            if not a.get('href'):
                continue

            text = a.get_text().strip()
            href_file = a['href'].split('/')[-1].strip()

            # If a link target filter is given, match the whole target url
            # against it.
            full_target_url = urljoin(base_url, a['href'])
            if link_target_filter:
                if not link_target_filter.fullmatch(full_target_url):
                    continue

            for (regex, pos) in regexs:
                pv, pc, psign = pos

                m = re.fullmatch(regex, text) or re.fullmatch(regex, href_file)
                if not m:
                    continue

                try:
                    v = VersionNumber(m[pv])
                except ValueError:
                    continue

                if v not in versions:
                    versions[v] = {}

                if pc and m[pc]:
                    comp = EXT_COMP_MAP[m[pc]]

                    if psign and m[psign]:
                        signatures[(v, comp)] = full_target_url
                    else:
                        versions[v][comp] = full_target_url

                elif psign and m[psign]:
                    signatures[v] = full_target_url

        # Add signature urls
        if not versions:
            return []

        composed = []
        for v, urls in versions.items():
            composed_urls = {}
            for comp, url in urls.items():
                sig_url = signatures.get((v, comp), signatures.get(v, None))

                # Remove /download from sourcefource file-list links
                if url and url.endswith('/download'):
                    url = url[:-9]

                if sig_url and sig_url.endswith('/download'):
                    sig_url = sig_url[:-9]

                composed_urls[comp] = (url, sig_url)

            composed.append((v, composed_urls))

        return composed
