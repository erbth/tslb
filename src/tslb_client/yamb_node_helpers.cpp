#include <new>
#include "yamb_node_helpers.h"
#include "BuildClusterProxy.h"

using namespace std;

connection_factory::~connection_factory()
{
}

yamb_node::connection *connection_factory::create_connection(string host, short port, string *error)
{
	return new connection(host, port);
}

connection::~connection()
{
	if (m_connect_cancellable)
		m_connect_cancellable->cancel();

	if (m_read_cancellable)
		m_read_cancellable->cancel();
}

connection::connection(string host, short port)
{
	m_socket_client = Gio::SocketClient::create();
	m_connect_cancellable = Gio::Cancellable::create();

	m_socket_client->connect_to_host_async(host, port, m_connect_cancellable,
			sigc::mem_fun(*this, &connection::async_connect_ready));
}

void connection::async_connect_ready(Glib::RefPtr<Gio::AsyncResult> async_result)
{
	try {
		m_connection = m_socket_client->connect_to_host_finish(async_result);
	} catch (Glib::Error &e) {
		if (e.code() != G_IO_ERROR_CANCELLED)
			set_connect_error(e.what());
		return;
	}

	if (!m_connection)
	{
		set_connect_error("m_connection is a nullptr ...");
		return;
	}

	m_connect_cancellable.reset();
	m_socket_client.reset();

	if (on_connected_callback)
		on_connected_callback();

	if (on_data_received_callback)
		start_reading();
}

void connection::set_connect_error(string e)
{
	connect_error = e;

	if (on_failed_to_connect_callback)
		on_failed_to_connect_callback(e);
}

void connection::disconnect()
{
	if (m_connection)
	{
		stop_reading();
		m_connection.reset();

		if (on_disconnected_callback)
			on_disconnected_callback();
	}
}

void connection::set_on_failed_to_connect_callback(on_failed_to_connect_callback_t cb)
{
	if (cb && !on_failed_to_connect_callback && connect_error)
	{
		on_failed_to_connect_callback = cb;
		cb(connect_error.value());
	}
	else
	{
		on_failed_to_connect_callback = cb;
	}
}

void connection::set_on_connected_callback(on_connected_callback_t cb)
{
	if (cb && !on_connected_callback && m_connection)
	{
		on_connected_callback = cb;
		cb();
	}
	else
	{
		on_connected_callback = cb;
	}
}

void connection::set_on_disconnected_callback(on_disconnected_callback_t cb)
{
	on_disconnected_callback = cb;
}


void connection::start_reading()
{
	if (!m_read_cancellable && m_connection)
	{
		m_read_cancellable = Gio::Cancellable::create();
		auto is = m_connection->get_input_stream();

		is->read_async(
				read_buffer, 10000,
				sigc::mem_fun(*this, &connection::async_read_ready),
				m_read_cancellable);
	}
}

void connection::stop_reading()
{
	if (m_read_cancellable)
	{
		m_read_cancellable->cancel();
		m_read_cancellable.reset();
	}
}

void connection::async_read_ready(Glib::RefPtr<Gio::AsyncResult> async_result)
{
	ssize_t count;

	try {
		count = m_connection->get_input_stream()->read_finish(async_result);
	} catch (Glib::Error &e) {
		if (e.code() != G_IO_ERROR_CANCELLED)
			disconnect();

		return;
	}

	if (count < 1)
	{
		disconnect();
		return;
	}

	if (on_data_received_callback)
		on_data_received_callback((uint8_t*) read_buffer, count);

	/* Start another read operation */
	m_read_cancellable = Gio::Cancellable::create();
	m_connection->get_input_stream()->read_async(
			read_buffer, 10000,
			sigc::mem_fun(*this, &connection::async_read_ready),
			m_read_cancellable);
}


void connection::set_on_data_received_callback(on_data_received_callback_t cb)
{
	on_data_received_callback = cb;

	if (cb != nullptr)
		start_reading();
	else
		stop_reading();
}

void connection::request_to_send_data(bool request_send)
{
	/* For now, use synchronous write operations. */
	if (request_send && on_ready_to_send_callback && m_connection)
		on_ready_to_send_callback();
}

void connection::set_on_ready_to_send_callback(on_ready_to_send_callback_t cb)
{
	on_ready_to_send_callback = cb;
}

size_t connection::send_data(const uint8_t *data, size_t count)
{
	if (count > 0)
	{
		ssize_t written = m_connection->get_output_stream()->write(data, count);

		if (written < 1)
		{
			disconnect();
			return 0;
		}

		return written;
	}
	else
		return count;
}


/* A yamb protocol to communicate with build nodes */
build_node_yamb_protocol::build_node_yamb_protocol(BuildClusterProxy::BuildClusterProxy &bcp)
	: build_cluster_proxy(bcp)
{
}

build_node_yamb_protocol::build_node_yamb_protocol(BuildClusterProxy::BuildClusterProxy &bcp,
		message_received_callback_t mrc)
	:
		build_cluster_proxy(bcp),
		message_received_callback(mrc)
{
}

build_node_yamb_protocol::~build_node_yamb_protocol()
{
}

uint32_t build_node_yamb_protocol::get_protocol_number() const
{
	return 1000;
}

void build_node_yamb_protocol::send_message(yamb_node::yamb_node *node,
		uint32_t destination, unique_ptr<yamb_node::stream> msg)
{
	node->send_message(move(msg), destination, get_protocol_number());
}

void build_node_yamb_protocol::message_received(
		yamb_node::yamb_node *node,
		uint32_t source,
		uint32_t destination,
		unique_ptr<yamb_node::stream> msg)
{
	if (source != node->get_current_address() && message_received_callback)
		message_received_callback(node, source, destination, move(msg));
}


/* A yamb protocol to communicate with build masters */
build_master_yamb_protocol::build_master_yamb_protocol(BuildClusterProxy::BuildClusterProxy &bcp)
	: build_cluster_proxy(bcp)
{
}

build_master_yamb_protocol::build_master_yamb_protocol(BuildClusterProxy::BuildClusterProxy &bcp,
		message_received_callback_t mrc)
	:
		build_cluster_proxy(bcp),
		message_received_callback(mrc)
{
}

build_master_yamb_protocol::~build_master_yamb_protocol()
{
}

uint32_t build_master_yamb_protocol::get_protocol_number() const
{
	return 1001;
}

void build_master_yamb_protocol::send_message(yamb_node::yamb_node *node,
		uint32_t destination, unique_ptr<yamb_node::stream> msg)
{
	node->send_message(move(msg), destination, get_protocol_number());
}

void build_master_yamb_protocol::message_received(
		yamb_node::yamb_node *node,
		uint32_t source,
		uint32_t destination,
		unique_ptr<yamb_node::stream> msg)
{
	if (source != node->get_current_address() && message_received_callback)
		message_received_callback(node, source, destination, move(msg));
}
