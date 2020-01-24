#ifndef __YAMB_NODE_HELPERS_H
#define __YAMB_NODE_HELPERS_H

#include <functional>
#include <glibmm.h>
#include <giomm.h>
#include <optional>
#include <yamb_node++.hpp>

/* Auxilary classes for the yamb node */

/* Prototypes */
class connection_factory;
class connection;
class build_node_yamb_protocol;

namespace BuildClusterProxy { class BuildClusterProxy; }

class connection_factory : public yamb_node::connection_factory
{
public:
	virtual ~connection_factory();

	yamb_node::connection *create_connection(std::string host, short port, std::string *error = nullptr) override;
};

class connection : public yamb_node::connection
{
private:
	/* Callbacks of the user */
	on_failed_to_connect_callback_t on_failed_to_connect_callback = nullptr;;
	on_connected_callback_t on_connected_callback = nullptr;
	on_disconnected_callback_t on_disconnected_callback = nullptr;

	on_data_received_callback_t on_data_received_callback = nullptr;
	on_ready_to_send_callback_t on_ready_to_send_callback = nullptr;

	/* For actually connecting */
	std::optional<std::string> connect_error;

	Glib::RefPtr<Gio::SocketClient> m_socket_client;
	Glib::RefPtr<Gio::Cancellable> m_connect_cancellable;
	Glib::RefPtr<Gio::SocketConnection> m_connection;

	void async_connect_ready(Glib::RefPtr<Gio::AsyncResult> async_result);
	void set_connect_error(std::string);

	void disconnect();

	/* For reading */
	Glib::RefPtr<Gio::Cancellable> m_read_cancellable;
	char read_buffer[10000];

	void start_reading();
	void stop_reading();
	void async_read_ready(Glib::RefPtr<Gio::AsyncResult> async_result);

public:
	connection(std::string host, short port);
	virtual ~connection();

	void set_on_failed_to_connect_callback(on_failed_to_connect_callback_t cb) override;
	void set_on_connected_callback(on_connected_callback_t cb) override;
	void set_on_disconnected_callback(on_disconnected_callback_t cb) override;

	void set_on_data_received_callback(on_data_received_callback_t cb) override;
	void request_to_send_data(bool request_send) override;
	void set_on_ready_to_send_callback(on_ready_to_send_callback_t cb) override;
	size_t send_data(const uint8_t *data, size_t count) override;
};


/* A yamb protocol to communicate with build ndoes */
class build_node_yamb_protocol : public yamb_node::yamb_protocol
{
private:
	using message_received_callback_t = std::function<void(yamb_node::yamb_node*,
			uint32_t source, uint32_t destination, std::unique_ptr<yamb_node::stream>)>;

	BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;

	message_received_callback_t message_received_callback;

public:
	build_node_yamb_protocol(BuildClusterProxy::BuildClusterProxy &bcp);
	build_node_yamb_protocol(BuildClusterProxy::BuildClusterProxy &bcp,
			message_received_callback_t mrc);

	virtual ~build_node_yamb_protocol();

	uint32_t get_protocol_number() const override;

	void send_message(yamb_node::yamb_node *node, uint32_t destination,
			std::unique_ptr<yamb_node::stream> msg);

	/* Called when a message addressed to this node was received. */
	void message_received(yamb_node::yamb_node *node, uint32_t source,
			uint32_t destination, std::unique_ptr<yamb_node::stream> msg) override;
};

#endif /* __YAMB_NODE_HELPERS_H */
