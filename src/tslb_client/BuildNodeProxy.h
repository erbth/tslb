#ifndef __BUILD_NODE_PROXY_H
#define __BUILD_NODE_PROXY_H

#include <rapidjson/document.h>
#include <string>
#include <utility>
#include <vector>

/* Invariants:
 *   * The BuildClusterProxy, to which a BuildNodeProxy is assigned, must live
 *     longer than the node proxy. */

namespace BuildClusterProxy { class BuildClusterProxy; }

namespace BuildNodeProxy
{
	/* Prototypes */
	class BuildNodeProxy;

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


	class ConsoleSubscriber
	{
		friend class BuildNodeProxy;

	private:
		BuildNodeProxy *node = nullptr;
		uint32_t last_mark_received = 0;

		void *priv = nullptr;

		/* Called when console data is received from the node.
		 * Initially all available (old) data is transfered to the subscriber
		 * through this cb.
		 *
		 * @param data: The data, do NOT consume, will be free'd afterwards /
		 *     could point to internal storage.
		 * @param size: Count of bytes in data */
		using new_data_cb_t = void(*)(void *priv, const char *data, size_t size);
		new_data_cb_t new_data_cb = nullptr;

		ConsoleSubscriber(BuildNodeProxy *node, new_data_cb_t new_data_cb, void *priv)
			: node(node), priv(priv), new_data_cb(new_data_cb) {}

	public:
		/* Only empty ConsoleSubscriber objects are publicly constructable. */
		ConsoleSubscriber() {};

		bool operator==(const ConsoleSubscriber &o) const
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

		/* Time of the last state query (should be done every 10 seconds to
		 * inform the node that the client is alive) */
		unsigned last_state_query = 0;

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

		/* A vector of console subscribers */
		std::vector<ConsoleSubscriber> console_subscribers;

	public:
		BuildNodeProxy(
				BuildClusterProxy::BuildClusterProxy &bcp,
				std::string identity,
				uint32_t yamb_addr);

		/* To be called every second */
		void timeout_1s();

		void set_yamb_addr(uint32_t addr);
		void message_received(rapidjson::Document&);

	private:
		/* This will alter the given document. */
		void send_message_to_node(rapidjson::Document&);

		/* Console streaming */
		void console_data_received(
			std::vector<std::pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size);

		void console_update_received(
			std::vector<std::pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size);

		void console_send_request_updates();
		void console_send_ack();
		void console_send_request(uint32_t start, uint32_t end);

	public:
		/* Does NOT free data. */
		void console_send_input(const char *data, size_t size);


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

		/* Subscribe to the current process's console output. @param priv is
		 * used to identify the subscription. It SHOULD NOT be nullptr as this
		 * indicates an empty / invalid ConsoleSubscriber object. If it is, an
		 * empty ConsoleSubscriber object is returned. */
		ConsoleSubscriber subscribe_to_console(ConsoleSubscriber::new_data_cb_t, void *priv);

		/* Unsubscribe from console output. The ConsoleSubscriber object given
		 * and all copies of it MUST NOT be used anymore afterwards. Therefore
		 * an internal pointer of the given object is set to nullptr. This does,
		 * however, not affect copies ... */
		void unsubscribe_from_console(ConsoleSubscriber&);

		void console_reconnect();
	};
}

#endif /* __BUILD_NODE_PROXY_H */
