#ifndef __BUILD_CLUSTER_PROXY_H
#define __BUILD_CLUSTER_PROXY_H

#include <map>
#include <memory>
#include <string>
#include <optional>
#include <utility>
#include <vector>
#include <yamb_node++.hpp>
#include "yamb_node_helpers.h"

namespace BuildNodeProxy { class BuildNodeProxy; }

namespace BuildClusterProxy
{
	/* Auxiliary classes for subscribing to a build cluster proxy.
	 * No two subscribers may use the same private data. This makes
	 * unsubscribing easier for subscribers. */
	struct ConnectionStateSubscriber
	{
		using on_established_t = void(*)(void*);
		using on_lost_t = void(*)(void*);
		using on_failed_t = void(*)(void*, std::string error);

		on_established_t on_established;
		on_lost_t on_lost;
		on_failed_t on_failed;

		void* priv;

		ConnectionStateSubscriber() :
			on_established(nullptr), on_lost(nullptr), on_failed(nullptr), priv(nullptr) {}

		ConnectionStateSubscriber(on_established_t a, on_lost_t b,
				on_failed_t c, void *d) :
			on_established(a), on_lost(b), on_failed(c), priv(d) {}

		bool operator==(const ConnectionStateSubscriber &o)
		{
			return priv == o.priv;
		}

		/* To construct an object for comparisons. */
		ConnectionStateSubscriber(void *priv)
			: on_established(nullptr),on_lost(nullptr),on_failed(nullptr),priv(priv) {}
	};

	struct BuildNodeListSubscriber
	{
		using on_list_changed_t = void(*)(void*);

		on_list_changed_t on_list_changed;

		void *priv;

		BuildNodeListSubscriber() : on_list_changed(nullptr), priv(nullptr) {}
		BuildNodeListSubscriber(on_list_changed_t a, void* p) : on_list_changed(a), priv(p) {}
		BuildNodeListSubscriber(void* p) : on_list_changed(nullptr), priv(p) {}

		bool operator==(const BuildNodeListSubscriber &o)
		{
			return priv == o.priv;
		}
	};

	class BuildClusterProxy
	{
	private:
		/* Properties of the build system proxied by you */
		std::map<std::string, std::shared_ptr<BuildNodeProxy::BuildNodeProxy>> build_nodes;
		std::vector<BuildNodeListSubscriber> build_node_list_subscribers;

		/* A soft timer that runs every second */
		bool soft_timeout_1s_handler();

	public:
		/* Communicating through the yamb */
		std::unique_ptr<yamb_node::yamb_node> ynode;
		std::shared_ptr<build_node_yamb_protocol> build_node_yprotocol;

	private:
		void on_connection_established();
		void on_connection_lost();
		void on_connection_failed(std::string error);

		unsigned build_nodes_last_searched = 10000;

		/* Other entities can subscribe to the connection status */
		std::vector<ConnectionStateSubscriber> connection_state_subscribers;


		/* Different actions */
		void search_for_build_nodes();

		/* Respond to messages from entities in the cluster */
		void build_node_message_received(
				yamb_node::yamb_node *node,
				uint32_t source, uint32_t destination,
				std::unique_ptr<yamb_node::stream> msg);

	public:
		BuildClusterProxy();

		/* Returns a string with an error message on failure and nullopt on
		 * success. */
		std::optional<std::string> connect_to_hub();

		void subscribe_to_connection_state(const ConnectionStateSubscriber &s);
		void unsubscribe_from_connection_state(void* priv);

		std::vector<std::string> list_build_nodes() const;
		std::vector<std::shared_ptr<BuildNodeProxy::BuildNodeProxy>> get_build_nodes() const;
		std::shared_ptr<BuildNodeProxy::BuildNodeProxy> get_build_node(std::string identity) const;

		void subscribe_to_build_node_list(const BuildNodeListSubscriber &s);
		void unsubscribe_from_build_node_list(void* priv);
	};
}

#endif /* __BUILD_CLUSTER_PROXY_H */
