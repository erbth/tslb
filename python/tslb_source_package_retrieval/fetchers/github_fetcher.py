"""
Fetch releases from GitHub
"""
import os
import re
import subprocess
import tempfile
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *


class GitHubFetcher(BaseFetcher):
    name = 'link_list'

    def handles_url(session, package_name, url, out):
        if url.startswith('https://github.com') and url.endswith('.git'):
            return True
        return False

    def fetch_versions(session, package_name, url, out, **kwargs):
        versions = []
        verbose = kwargs.pop('verbose', False)
        only_n_newest = kwargs.pop('only_n_newest', 5)

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

            if probe_url(session, release_url):
                releases.append((tag, v, v_str, release_url))

        if not releases:
            return []


        # Case 1: conventional autotools source packages uploaded as assets.
        latest_sig_found = False
        first = True

        for tag, v, v_str, release_url in releases:
            # Probe a few filenames
            found = False
            for ext in ['tar.xz', 'tar.bz2', 'tar.gz', 'tgz', 'tar.lz', 'tar.zstd']:
                download_url = url.replace('.git', '/releases/download/%s/%s-%s.%s' %
                        (tag, package_name, v_str, ext))

                if verbose:
                    print("  Probing '%s' ..." % download_url)

                if probe_url(session, download_url):
                    found = True

                    # Try to find signature
                    sig_found = False
                    for sig_ext in ['sig', 'sign', 'asc']:
                        signature_download_url = download_url + '.' + sig_ext

                        print("  Probing '%s' ..." % signature_download_url)
                        if probe_url(session, signature_download_url):
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
            return []
