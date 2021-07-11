# A list of all version fetchers in the order in which they shall be queried.
from .base_fetcher import *

from .link_list_fetcher import LinkListFetcher
from .github_fetcher import GitHubFetcher


ALL_FETCHERS = [
    GitHubFetcher,
    LinkListFetcher
]
