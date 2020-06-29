#ifndef __BUILD_MASTER_PROXY_H
#define __BUILD_MASTER_PROXY_H

#include <rapidjson/document.h>
#include <set>
#include <string>
#include <utility>
#include <vector>
#include "utilities.h"

/* Invariants:
 *   * The BuildClusterProxy, to which a BuildMasterProxy is assigned, must live
 *     longer than the master proxy. */

namespace BuildClusterProxy { class BuildClusterProxy; }

namespace BuildMasterProxy
{
	/* Prototypes */
	class BuildMasterProxy;

	enum state
	{
		BMP_STATE_OFF,
		BMP_STATE_IDLE,
		BMP_STATE_COMPUTING,
		BMP_STATE_BUILDING,
		BMP_STATE_INVALID = 100
	};

	/**
	 * Two StateSubscribers are identical if they have the same private data
	 * pointer. */
	struct Subscriber
	{
		using on_responding_changed_t = void(*)(void *priv);
		using on_remaining_changed_t = void(*)(void *priv);
		using on_build_queue_changed_t = void(*)(void *priv);
		using on_building_set_changed_t = void(*)(void *priv);
		using on_nodes_changed_t = void(*)(void *priv);
		using on_state_changed_t = void(*)(void *priv);
		using on_error_received_t = void(*)(void *priv, std::string error_msg);


		on_responding_changed_t on_responding_changed = nullptr;
		on_remaining_changed_t on_remaining_changed = nullptr;
		on_build_queue_changed_t on_build_queue_changed = nullptr;
		on_building_set_changed_t on_building_set_changed = nullptr;
		on_nodes_changed_t on_nodes_changed = nullptr;
		on_state_changed_t on_state_changed = nullptr;
		on_error_received_t on_error_received = nullptr;

		void *priv = nullptr;

		Subscriber(
				on_responding_changed_t a,
				on_remaining_changed_t b,
				on_build_queue_changed_t c,
				on_building_set_changed_t d,
				on_nodes_changed_t e,
				on_state_changed_t f,
				on_error_received_t g,
				void *p)
			:
				on_responding_changed(a),
				on_remaining_changed(b),
				on_build_queue_changed(c),
				on_building_set_changed(d),
				on_nodes_changed(e),
				on_state_changed(f),
				on_error_received(g),
				priv(p)
		{
		}

		Subscriber(void *p) : priv(p) {}

		bool operator==(const Subscriber &o) const
		{
			return priv == o.priv;
		}
	};


	class ConsoleSubscriber
	{
		friend class BuildMasterProxy;

	private:
		BuildMasterProxy *master = nullptr;
		uint32_t last_mark_received = 0;

		void *priv = nullptr;

		/* Called when console data is received from the master.
		 * Initiallly all available (old) data is transfered to the subscriber
		 * through this cb.
		 *
		 * @param data: The data, do NOT consume, will be free'd afterwards /
		 *     could point to internal storage.
		 * @param size: Count of bytes in data */
		using new_data_cb_t = void(*)(void *priv, const char *data, size_t size);
		new_data_cb_t new_data_cb = nullptr;

		ConsoleSubscriber(BuildMasterProxy *master, new_data_cb_t new_data_cb, void *priv)
			: master(master), priv(priv), new_data_cb(new_data_cb) {}

	public:
		/* Only empty ConsoleSubscriber objects are publicly constructable. */
		ConsoleSubscriber() {};

		bool operator==(const ConsoleSubscriber &o) const
		{
			return priv == o.priv;
		}
	};


	class BuildMasterProxy
	{
	private:
		/* Time of last state update in seconds from now */
		unsigned last_response = 10000;
		unsigned last_refresh_sent = 10000;

	public:
		const std::string identity;

	private:
		BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;
		uint32_t current_yamb_address;

		/* State */
		std::set<std::pair<std::string, std::string>> remaining;
		std::vector<std::pair<std::string, std::string>> build_queue;
		std::set<std::pair<std::string, std::string>> building_set;
		std::vector<std::string> idle_nodes;
		std::vector<std::string> busy_nodes;

		enum state state = BMP_STATE_OFF;
		enum architecture architecture = ARCH_I386;
		bool error = false;
		bool valve = false;

		/* Different actions */

		/* A list of entities that subscribe to your state. */
		std::vector<Subscriber> subscribers;

		/* A vector of console subscribers */
		std::vector<ConsoleSubscriber> console_subscribers;

	public:
		BuildMasterProxy(
				BuildClusterProxy::BuildClusterProxy &bcp,
				std::string identity,
				uint32_t yamb_addr);

		/* To be called every second */
		void timeout_1s();

		void set_yamb_addr(uint32_t addr);
		void message_received(rapidjson::Document&);

	private:
		/* This will alter the given document. */
		void send_message_to_master(rapidjson::Document&);

		void send_get_state();
		void send_get_remaining();
		void send_get_build_queue();
		void send_get_building_set();
		void send_get_nodes();
		void send_subscribe();

		/* Console streaming */
		void console_data_received(
			std::vector<std::pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size);

		void console_update_received(
			std::vector<std::pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size);

		void console_send_request_updates();
		void console_send_ack();
		void console_send_request(uint32_t start, uint32_t end);

	public:
		/* Querying state */
		bool is_responding() const;

		const std::set<std::pair<std::string, std::string>> &get_remaining() const;
		const std::vector<std::pair<std::string, std::string>> &get_build_queue() const;
		const std::set<std::pair<std::string, std::string>> &get_building_set() const;
		const std::vector<std::string> &get_idle_nodes() const;
		const std::vector<std::string> &get_busy_nodes() const;

		enum state get_state() const;
		enum architecture get_architecture() const;
		bool get_error() const;
		bool get_valve() const;

		/* Objects can subscribe to the build master (proxy). */
		void subscribe(const Subscriber &s);
		void unsubscribe(void *priv);

		/* Different actions */
		void refresh();
		void start(enum architecture arch);
		void stop();
		void open();
		void close();

		/* Console streaming */
		/* Subscribe to the build master's console output. @param priv is used
		 * to identify the subscription. It SHOULD NOT be nullptr as this
		 * indicates an empty / invalid ConsoleSubscriber object. If it is, an
		 * empty ConsoleSubscriber object is returned. */
		ConsoleSubscriber subscribe_to_console(ConsoleSubscriber::new_data_cb_t, void *priv);

		/* Unsubscribe from console output. The ConsoleSubscriber object given
		 * and all copies of it MUST NOT be used anymore afterwards. Therefore
		 * an internal pointer oft he given object is set to nullptr. This does,
		 * however, not affect copies ... */
		void unsubscribe_from_console(ConsoleSubscriber&);

		void console_reconnect();
	};
}

#endif /* __BUILD_MASTER_PROXY_H */
