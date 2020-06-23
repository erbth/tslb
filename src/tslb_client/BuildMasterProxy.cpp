#include "BuildMasterProxy.h"
#include "BuildClusterProxy.h"

using namespace std;

namespace BuildMasterProxy
{

BuildMasterProxy::BuildMasterProxy(
		BuildClusterProxy::BuildClusterProxy &bcp,
		string identity,
		uint32_t yamb_addr)
	:
		identity(identity),
		build_cluster_proxy(bcp),
		current_yamb_address(yamb_addr)
{
	refresh();
}


void BuildMasterProxy::refresh()
{
	/* TODO */
}


void BuildMasterProxy::timeout_1s()
{
	/* TODO */
}


void BuildMasterProxy::set_yamb_addr(uint32_t addr)
{
	if (addr != current_yamb_address)
	{
		current_yamb_address = addr;

		/* The master may have been restarted */
		refresh();
	}
}


void BuildMasterProxy::message_received(rapidjson::Document& d)
{
}

}
