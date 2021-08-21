#!/usr/bin/python3
"""
Download missing archives
"""
import os
import subprocess
import sys
import tslb.database as db
import tslb.database.upstream_versions as dbuv
import urllib.parse
from sqlalchemy.orm import aliased
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb import SourcePackage as spkg
from tslb import settings
from tslb.Console import Color
from tslb.parse_utils import is_yes, query_user_input
from tslb_source_package_retrieval.fetchers.base_fetcher import parse_querystring


def check_for_missing_archives(arch):
    # [(url, signature url)]
    archive_urls = []

    # Collect archives to download
    names = spkg.SourcePackageList(arch).list_source_packages()
    i = 0
    while i < len(names):
        name = names[i]

        sp = spkg.SourcePackage(name, arch)
        spv = None
        for v in sp.list_version_numbers():
            spv = sp.get_version(v)
            if is_yes(spv.get_attribute_or_default('enabled', 'false')):
                if spv.has_attribute('source_archive'):
                    archive = spv.get_attribute('source_archive')

                    if not archive:
                        continue

                    # Check if the archive is in the source_location
                    if os.path.exists(os.path.join(settings.get_source_location(), archive)):
                        print(Color.GREEN + "`%s's source archive exists" % spv + Color.NORMAL)
                    else:
                        print("`%s' source archive (%s) does not exist." % (spv, archive))

                        # Check if the archive can be downloaded
                        with db.session_scope() as s:
                            a = aliased(dbuv.UpstreamVersion)
                            uv = s.query(a)\
                                    .filter(a.name == sp.name,
                                            a.version_number == spv.version_number)\
                                    .first()

                            if uv:
                                if '.git' in uv.download_url or \
                                        archive.endswith('.tar') or \
                                        urllib.parse.unquote(uv.download_url.split('/')[-1]) == archive:
                                    print("  Archive available from '%s'." % uv.download_url)
                                    if query_user_input("  select to download?", "yN") == 'y':
                                        archive_urls.append(
                                            (uv.download_url, uv.signature_download_url))

                                else:
                                    print(Color.RED + "  Available archive does not "
                                            "match configured archive:" + Color.NORMAL)
                                    print("  '%s' differs from '%s'" % (uv.download_url, archive))

                                    r = query_user_input("  download anyway (yes/no/retry)?", "ynR")
                                    if r == 'r':
                                        i -= 1
                                        print()
                                        break

                                    elif r == 'y':
                                        archive_urls.append(
                                            (uv.download_url, uv.signature_download_url))

                            else:
                                print(Color.RED + "  No archive available." + Color.NORMAL)
                                if query_user_input("  abort?", "yN") == 'y':
                                    print("User aborted.")
                                    exit(1)

                        print()

                else:
                    print(Color.YELLOW + "WARNING: `%s' has no `source_archive' attribute." %
                            spv + Color.NORMAL)

        del spv
        del sp
        i += 1


    # Ask for confirmation
    if not archive_urls:
        return

    print("The following archives will be downloaded:")
    for url, sig_url in archive_urls:
        print("    %s%s" % (url, (" (signature: %s)" % sig_url) if sig_url else ""))

    print("\n")
    if query_user_input("Continue?", "yn") == 'n':
        return

    # Download selected archives.
    staging_location = os.path.join(settings.get_source_location(), 'staging')
    git_location = os.path.join(staging_location , 'git')
    signed_location = os.path.join(staging_location, 'signed')
    unsigned_location = os.path.join(staging_location, 'unsigned')
    checksum_location = os.path.join(staging_location, 'checksumed')

    def _download(url, dest):
        os.makedirs(dest, mode=0o755, exist_ok=True)

        print("Downloading '%s'..." % url)
        cmd = ['wget', url]
        ret = subprocess.run(cmd, cwd=dest)
        if ret.returncode != 0:
            raise ces.CommandFailed(cmd, ret.returncode)


    for url, sig_url in archive_urls:
        # Download URLs must use https.
        if not url.startswith('https') and (not sig_url or not sig_url.startswith('http')):
            print(Color.RED + "ERROR: URL '%s' does not use scheme https and no signature "
                    "URL given. Skipping." % url + Color.NORMAL)
            continue

        if not url.startswith('https'):
            print(Color.ORANGE + "WARNING: URL '%s' does not use scheme https." %
                    url + Color.NORMAL)

        url, params = parse_querystring(url)

        if url.endswith('.git'):
            # Git repo
            os.makedirs(git_location, mode=0o755, exist_ok=True)

            print("Cloning '%s'..." % url)
            cmd = ['git', 'clone', url]
            ret = subprocess.run(cmd, cwd=git_location)
            if ret.returncode != 0:
                raise ces.CommandFailed(cmd, ret.returncode)

            tag = params['tag']
            repo_name = url.split('/')[-1].replace('.git', '')
            print("Checking out tag '%s'..." % tag)
            cmd = ['git', 'checkout', tag]
            ret = subprocess.run(cmd, cwd=os.path.join(git_location, repo_name))
            if ret.returncode != 0:
                raise ces.CommandFailed(cmd, ret.returncode)

        elif sig_url and sig_url.startswith('http'):
            # Conventional case, both archvie and signature are available:
            if not sig_url.startswith('http'):
                print(Color.YELLOW + "WARNING: Signature URL '%s' does not use scheme https. Skipping." %
                        sig_url + Color.NORMAL)
                continue

            # Download archive and signature
            _download(url, signed_location)
            _download(sig_url, signed_location)

        elif sig_url and sig_url.startswith('sha'):
            parts = sig_url.split(':')
            alg = parts[0]
            sig = ':'.join(parts[1:])

            # Checksum-urls
            _download(url, checksum_location)
            with open(
                    os.path.join(checksum_location, url.split('/')[-1] + '.' + alg),
                    'wb') as f:
                f.write(sig.lower().encode('ascii'))

        elif sig_url:
            print(Color.RED + "ERROR: Invalid signature URL: '%s'" + sig_url + Color.NORMAL)
            exit(1)

        else:
            # No signature
            _download(url, unsigned_location)


# Download archives
def main():
    if len(sys.argv) != 2:
        print("Usage: %s <architecture>" % sys.argv[0])
        exit(1)

    try:
        arch = Architecture.to_int(sys.argv[1])
    except ValueError:
        print(str(e))
        exit(1)

    print("Checking for missing archives of enabled source package versions...")
    check_for_missing_archives(arch)

if __name__ == '__main__':
    main()
    exit(0)
