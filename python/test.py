from tslb_source_package_retrieval import fetch_upstream_versions
from tslb.SourcePackage import SourcePackage

fetch_upstream_versions.fetch_versions_for_package(SourcePackage('nghttp2', 'amd64'))
