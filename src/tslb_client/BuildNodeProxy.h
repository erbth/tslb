#ifndef __BUILD_NODE_PROXY_H
#define __BUILD_NODE_PROXY_H

#include <rapidjson/document.h>
#include <string>

/* Invariants:
 *   * The BuildClusterProxy, to which a BuildNodeProxy is assigned, must live
 *     longer than the node proxy. */

namespace BuildClusterProxy { class BuildClusterProxy; }

namespace BuildNodeProxy
{
	enum State
	{
		STATE_IDLE = 0,
		STATE_BUILDING,
		STATE_FINISHED,
		STATE_FAILED,
		STATE_MAINTENANCE,
		STATE_UNKNOWN = 100
	};

	struct StateSubscriber
	{
		using on_responding_changed_t = void(*)(void *priv, bool responding);
		using on_state_changed_t = void(*)(void*priv, State state);
		using on_error_received_t = void(*)(void*priv, std::string err);

		on_responding_changed_t on_responding_changed = nullptr;
		on_state_changed_t on_state_changed = nullptr;
		on_error_received_t on_error_received = nullptr;

		void *priv = nullptr;

		StateSubscriber(on_responding_changed_t a, on_state_changed_t b, on_error_received_t c, void *p)
			: on_responding_changed(a), on_state_changed(b), on_error_received(c), priv(p) {}

		StateSubscriber(void *p) : priv(p) {}

		bool operator==(const StateSubscriber &o)
		{
			return priv == o.priv;
		}
	};

	class BuildNodeProxy
	{
	private:
		/* Not sure if this would be helpful since I want as much work as
		 * possible to be done here to reduce complexity in one source file. */
		// friend BuildClusterProxy::BuildClusterProxy;

		/* Time of last state update in seconds from now */
		unsigned last_state_update = 0;

	public:
		const std::string identity;

	private:
		BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;
		uint32_t current_yamb_address;

		enum State state = STATE_UNKNOWN;

		/* Extended state ;-) */
		std::string pkg_name;
		std::string pkg_arch;
		std::string pkg_version;
		std::string fail_reason;

		/* Different actions */
		void query_state();

		/* A list of entities that subscribe to your state. */
		std::vector<StateSubscriber> state_subscribers;

	public:
		BuildNodeProxy(
				BuildClusterProxy::BuildClusterProxy &bcp,
				std::string identity,
				uint32_t yamb_addr);

		/* To be called every second */
		void timeout_1s();

		void set_yamb_addr(uint32_t addr);
		void message_received(rapidjson::Document&);

		bool is_responding() const;
		enum State get_state() const;

		std::string get_pkg_name() const;
		std::string get_pkg_arch() const;
		std::string get_pkg_version() const;
		std::string get_fail_reason() const;

		/* Objects can subscribe to the build node's (proxy's) state. */
		void subscribe_to_state(const StateSubscriber &s);
		void unsubscribe_from_state(void *priv);

		/* More actions */
		void request_start_build(std::string name, std::string arch, std::string version);
		void request_abort_build();
		void request_reset();
		void request_enable_maintenance();
		void request_disable_maintenance();
	};
}

#endif /* __BUILD_NODE_PROXY_H */
