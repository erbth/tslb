#ifndef __BUILD_MASTER_PROXY_H
#define __BUILD_MASTER_PROXY_H

#include <rapidjson/document.h>
#include <string>

/* Invariants:
 *   * The BuildClusterProxy, to which a BuildMasterProxy is assigned, must live
 *     longer than the master proxy. */

namespace BuildClusterProxy { class BuildClusterProxy; }

namespace BuildMasterProxy
{
	class BuildMasterProxy
	{
	private:
		/* Time of last state update in seconds from new */
		unsigned last_state_update = 0;

	public:
		const std::string identity;

	private:
		BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;
		uint32_t current_yamb_address;

		/* Different actions */
		void refresh();

	public:
		BuildMasterProxy(
				BuildClusterProxy::BuildClusterProxy &bcp,
				std::string identity,
				uint32_t yamb_addr);

		/* To be called every second */
		void timeout_1s();

		void set_yamb_addr(uint32_t addr);
		void message_received(rapidjson::Document&);
	};
}

#endif /* __BUILD_MASTER_PROXY_H */
