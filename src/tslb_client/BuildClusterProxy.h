#ifndef __BUILD_CLUSTER_PROXY_H
#define __BUILD_CLUSTER_PROXY_H

#include <map>
#include <memory>
#include <string>
#include <optional>
#include <utility>
#include <vector>
#include <yamb_node++.hpp>

class BuildNodeProxy;
class build_node_yamb_protocol;

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

	class BuildClusterProxy
	{
	private:
		std::map<std::string, std::shared_ptr<BuildNodeProxy>> build_nodes;

		/* Communicating through the yamb */
		std::unique_ptr<yamb_node::yamb_node> ynode;

		void on_connection_established();
		void on_connection_lost();
		void on_connection_failed(std::string error);

		std::shared_ptr<build_node_yamb_protocol> build_node_yprotocol;

		/* Other entities can subscribe to the connection status */
		std::vector<ConnectionStateSubscriber> connection_state_subscribers;


		/* Different actions */
		void search_for_build_nodes();

	public:
		/* Returns a string with an error message on failure and nullopt on
		 * success. */
		std::optional<std::string> connect_to_hub();

		void subscribe_to_connection_state(const ConnectionStateSubscriber &s);
		void unsubscribe_from_connection_state(void* priv);

		std::vector<std::string> list_build_nodes() const;
		std::vector<std::shared_ptr<BuildNodeProxy>> get_build_nodes() const;
	};
}

#endif /* __BUILD_CLUSTER_PROXY_H */
