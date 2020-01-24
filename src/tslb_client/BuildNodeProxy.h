#ifndef __BUILD_NODE_PROXY_H
#define __BUILD_NODE_PROXY_H

#include <string>

/* Invariants:
 *   * The BuildClusterProxy, to which a BuildNodeProxy is assigned, must live
 *     longer than the node proxy. */

namespace BuildClusterProxy { class BuildClusterProxy; }

class BuildNodeProxy
{
private:
	friend BuildClusterProxy::BuildClusterProxy;

	std::string identity;
	BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;

public:
	BuildNodeProxy(BuildClusterProxy::BuildClusterProxy &bcp, std::string identity);

	std::string get_identity() const;
};

#endif /* __BUILD_NODE_PROXY_H */
