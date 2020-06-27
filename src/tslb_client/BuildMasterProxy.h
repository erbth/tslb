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
	};
}

#endif /* __BUILD_MASTER_PROXY_H */
