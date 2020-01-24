#include "BuildNodeProxy.h"

using namespace std;

BuildNodeProxy::BuildNodeProxy(BuildClusterProxy::BuildClusterProxy &bcp, string identity)
	: identity(identity), build_cluster_proxy(bcp)
{
}

string BuildNodeProxy::get_identity() const
{
	return identity;
}
