"""
Fetch tags from a git repository.
"""
import re
import subprocess
from tslb.VersionNumber import VersionNumber
from .base_fetcher import *


class GitTagFetcher(BaseFetcher):
    name = 'git_tag'

    def handles_url(session, package_name, url, out):
        return url.startswith('https://') and url.endswith('.git')

    def fetch_versions(session, package_name, url, out, **kwargs):
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


        # Sort out tags that cannot be interpretted as version numbers or that
        # seem to belong to release candidates or represent timestamps
        annotated_tags = []
        for tag in tags:
            # Skip release candidates
            if 'rc' in tag.lower():
                continue

            v_str = None

            print(tag)
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
                annotated_tags.append((VersionNumber(v_str), tag))

        annotated_tags.sort()
        annotated_tags.reverse()

        # Add urls
        for v, tag in annotated_tags:
            versions.append((v, {'git': (url + "?tag=" + tag, None)}))

        return versions
