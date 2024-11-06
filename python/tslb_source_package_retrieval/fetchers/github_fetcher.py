"""
Fetch releases from GitHub
"""
import requests.exceptions
import os
import re
import subprocess
import tempfile
from tslb import parse_utils
from tslb.Console import Color
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *


class GitHubFetcher(BaseFetcher):
    name = 'github'

    def handles_url(session, package_name, url, out):
        url, params = parse_querystring(url)
        if url.startswith('https://github.com') and url.endswith('.git'):
            return True
        return False

    def fetch_versions(session, package_name, url, out, **kwargs):
        # Interpret URL
        url, params = parse_querystring(url)

        tag_pattern = params.get('tag_pattern')
        if tag_pattern:
            tag_pattern = re.compile(tag_pattern)

        artifact_file_format = params.get('artifact_file_format')

        versions = []
        verbose = kwargs.pop('verbose', False)

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
            if 'rc' in tag.lower() or 'pre' in tag.lower():
                continue

            # Skip filtered tags if a filter pattern is set
            if tag_pattern:
                if not tag_pattern.fullmatch(tag):
                    continue

            v_str = None

            # classical v...
            m = re.match(r'^v?([0-9]+(\.[0-9a-zA-Z.]+)?)$', tag)
            if m:
                v_str = m[1]

            # Used by intel and others
            if not v_str:
                m = re.match(r'^.*[a-zA-Z]-([0-9]+(\.[0-9]+)*)$', tag)
                if m:
                    v_str = m[1]

            # Used e.g. by ICU
            if not v_str:
                m = re.match(r'^.*[a-zA-Z]-(([0-9]+)(-[0-9]+)+)$', tag)
                if m:
                    v_str = m[1].replace('-', '.')

            # Used by expat
            if not v_str:
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

        # Find GitHub Releases for tags; only consider 5 newest releases
        # releases is a list [(release tag name, version, release description)]
        releases = []
        repo_parts = re.fullmatch(r'https://github.com/([^/]+)/([^/]+)\.git', url)
        if not repo_parts:
            raise UnknownWebpageFormat(url, "Cannot split github url into owner and repo")

        rel_url = 'https://api.github.com/repos/%s/%s/releases?per_page=10' % (
                repo_parts[1], repo_parts[2])

        try:
            rel_descs = download_url(session, rel_url).json()
        except requests.exceptions.JSONDecodeError as exc:
            raise LoadError(url, str(exc))

        if not isinstance(rel_descs, list):
            raise LoadError(url, "Failed to fetch GitHub releases")

        # Make sure only 5 releases are considered
        rel_descs = rel_descs[:5]

        for v, v_str, tag in annotated_tags:
            if not rel_descs:
                break

            to_remove = 0
            for desc in list(rel_descs):
                to_remove += 1
                if desc.get('tag_name') == tag:
                    releases.append((tag, v, v_str, desc))
                    rel_descs = rel_descs[to_remove:]
                    break

        if not releases:
            print(Color.YELLOW + "\nWARNING: Package `%s' uses "
                        "`github'-fetcher but has no releases. Maybe try using "
                        "`git_tag'-fetcher instead." % package_name +
                        Color.NORMAL,
                    file=out)

            return []


        # Case 1: conventional autotools source packages uploaded as assets.
        latest_sig_found = False
        first = True

        for tag, v, v_str, rel_desc in releases:
            # Probe a few filenames
            asset_urls = [a['browser_download_url']
                          for a in rel_desc.get('assets', [])
                          if a.get('browser_download_url')]

            # For format regexes
            tmpl_ctx = {
                    'VERSION': re.escape(v_str)
            }

            found = False
            for ext in ['tar.xz', 'tar.bz2', 'tar.gz', 'tgz', 'tar.lz', 'tar.zstd']:
                if artifact_file_format:
                    artifact_url = None
                    for a in asset_urls:
                        m = re.match(
                                    re.escape(url.replace('.git', '/releases/download/%s/' % tag)) +
                                    artifact_file_format % tmpl_ctx,
                                a)

                        if m:
                            artifact_url = a
                            break

                    if not artifact_url:
                        raise LoadError(url, "Failed to find asset which "
                                        "matches artifact_file_format")

                else:
                    artifact_url = url.replace('.git', '/releases/download/%s/%s-%s.%s' %
                            (tag, package_name, v_str, ext))

                if artifact_url in asset_urls:
                    found = True

                    # Try to find signature
                    sig_found = False
                    for sig_ext in ['sig', 'sign', 'asc']:
                        signature_artifact_url = artifact_url + '.' + sig_ext

                        if signature_artifact_url in asset_urls:
                            sig_found = True
                            if first:
                                latest_sig_found = True

                            break

                    versions.append((v, {
                        EXT_COMP_MAP[ext]: (artifact_url, signature_artifact_url if sig_found else None)
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
        for tag, v, v_str, release_url in releases:
            with tempfile.TemporaryDirectory() as tmpdir:
                ret = subprocess.run(['git', 'clone', '--bare', url,
                                      '--single-branch', '--depth=1',
                                      '--branch=' + tag, 'repo'], cwd=tmpdir)

                if ret.returncode != 0:
                    raise LoadError(url, "git clone --bare failed with code %s." % ret.returncode)

                repo_dir = os.path.join(tmpdir, 'repo')

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
            return []
