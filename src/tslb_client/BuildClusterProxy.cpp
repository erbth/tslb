#include <algorithm>
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include "BuildClusterProxy.h"
#include "yamb_node_helpers.h"

using namespace std;
using namespace rapidjson;

namespace BuildClusterProxy
{

void BuildClusterProxy::on_connection_established()
{
	for_each(
			connection_state_subscribers.cbegin(),
			connection_state_subscribers.cend(),
			[](const ConnectionStateSubscriber &s)
			{
				if (s.on_established)
					s.on_established(s.priv);
			});

	/* Search for build nodes */
	search_for_build_nodes();
}

void BuildClusterProxy::on_connection_lost()
{
	for_each(
			connection_state_subscribers.cbegin(),
			connection_state_subscribers.cend(),
			[](const ConnectionStateSubscriber &s)
			{
				if (s.on_lost)
					s.on_lost(s.priv);
			});
}

void BuildClusterProxy::on_connection_failed(string error)
{
	for_each(
			connection_state_subscribers.cbegin(),
			connection_state_subscribers.cend(),
			[&error](const ConnectionStateSubscriber &s)
			{
				if (s.on_failed)
					s.on_failed(s.priv, error);
			});
}

optional<string> BuildClusterProxy::connect_to_hub()
{
	if (!ynode)
	{
		ynode = unique_ptr<yamb_node::yamb_node>(yamb_node::yamb_node::create_yamb_node(
				make_shared<connection_factory>(),
				"::1", 0));

		if (!build_node_yprotocol)
			build_node_yprotocol = make_shared<build_node_yamb_protocol>(*this);

		ynode->register_protocol(build_node_yprotocol);

		ynode->add_on_connection_established_callback(
				bind(&BuildClusterProxy::on_connection_established, this));

		ynode->add_on_connection_lost_callback(
				bind(&BuildClusterProxy::on_connection_lost, this));

		ynode->add_on_connection_failed_callback(
				bind(&BuildClusterProxy::on_connection_failed, this, std::placeholders::_1));
	}

	if (!ynode->connect_to_hub())
		return ynode->get_connection_error_message();
	else
		return nullopt;
}

void BuildClusterProxy::subscribe_to_connection_state(const ConnectionStateSubscriber &s)
{
	if (s.on_established || s.on_lost || s.on_failed)
		connection_state_subscribers.push_back(s);
}

void BuildClusterProxy::unsubscribe_from_connection_state(void* priv)
{
	auto i = find(
			connection_state_subscribers.begin(),
			connection_state_subscribers.end(),
			ConnectionStateSubscriber(priv));

	if (i != connection_state_subscribers.end())
		connection_state_subscribers.erase(i);
}


/* Different actions */
void BuildClusterProxy::search_for_build_nodes()
{
	if (ynode)
	{
		auto msg = make_unique<yamb_node::stream>();

		Document d;
		d.SetObject();
		d.AddMember("action", "identify", d.GetAllocator());

		StringBuffer buffer;
		Writer<StringBuffer> writer(buffer);
		d.Accept(writer);

		msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());

		build_node_yprotocol->send_message(ynode.get(), 0xffffffff, move(msg));
	}
}


vector<string> BuildClusterProxy::list_build_nodes() const
{
	vector<string> v;

	for_each(build_nodes.cbegin(), build_nodes.cend(),
			[&v](pair<string,shared_ptr<BuildNodeProxy>> t) { v.push_back(t.first); });

	return v;
}

vector<shared_ptr<BuildNodeProxy>> BuildClusterProxy::get_build_nodes() const
{
	vector<shared_ptr<BuildNodeProxy>> v;

	for_each(build_nodes.cbegin(), build_nodes.cend(),
			[&v](pair<string,shared_ptr<BuildNodeProxy>> t) { v.push_back(t.second); });

	return v;
}

}
