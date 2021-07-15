# A list of all version fetchers in the order in which they shall be queried.
from .base_fetcher import *

from .link_list_fetcher import LinkListFetcher
from .version_directory_links_fetcher import VersionDirectoryLinksFetcher
from .github_fetcher import GitHubFetcher
from .git_tag_fetcher import GitTagFetcher
from .kernel_org_fetcher import KernelOrgFetcher
from .sqlite_fetcher import SQLiteFetcher


ALL_FETCHERS = [
    SQLiteFetcher,
    KernelOrgFetcher,
    GitHubFetcher,
    GitTagFetcher,
    VersionDirectoryLinksFetcher,
    LinkListFetcher,
]
