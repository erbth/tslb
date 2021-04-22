#include <algorithm>
#include <cstdio>
#include <rapidjson/document.h>
#include <rapidjson/error/en.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include "BuildClusterProxy.h"
#include "BuildNodeProxy.h"
#include "BuildMasterProxy.h"
#include "yamb_node_helpers.h"

using namespace std;
using namespace rapidjson;

namespace BuildClusterProxy
{

BuildClusterProxy::BuildClusterProxy()
{
	Glib::signal_timeout().connect(
			sigc::mem_fun(*this, &BuildClusterProxy::soft_timeout_1s_handler),
			1000);
}

bool BuildClusterProxy::soft_timeout_1s_handler()
{
	if (++build_nodes_last_searched >= 30)
		search_for_build_nodes();

	if (++build_masters_last_searched >= 30)
		search_for_build_masters();

	for_each(
			build_nodes.begin(), build_nodes.end(),
			[](pair<string,shared_ptr<BuildNodeProxy::BuildNodeProxy>> p){ p.second->timeout_1s(); });

	for_each(
			build_masters.begin(), build_masters.end(),
			[](pair<string,shared_ptr<BuildMasterProxy::BuildMasterProxy>> p){ p.second->timeout_1s(); });

	return true;
}

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
	search_for_build_masters();
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

optional<string> BuildClusterProxy::connect_to_hub(const string& yamb_addr)
{
	if (!ynode)
	{
		ynode = unique_ptr<yamb_node::yamb_node>(yamb_node::yamb_node::create_yamb_node(
				make_shared<connection_factory>(),
				yamb_addr.c_str(), 0));

		if (!build_node_yprotocol)
			build_node_yprotocol = make_shared<build_node_yamb_protocol>(
					*this, bind(
						&BuildClusterProxy::build_node_message_received,
						this,
						placeholders::_1,
						placeholders::_2,
						placeholders::_3,
						placeholders::_4));

		ynode->register_protocol(build_node_yprotocol);

		if (!build_master_yprotocol)
			build_master_yprotocol = make_shared<build_master_yamb_protocol>(
					*this, bind(
						&BuildClusterProxy::build_master_message_received,
						this,
						placeholders::_1,
						placeholders::_2,
						placeholders::_3,
						placeholders::_4));

		ynode->register_protocol(build_master_yprotocol);

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


/* Respond to messages from different entities in the cluster */
void BuildClusterProxy::build_node_message_received(
		yamb_node::yamb_node *nodes,
		uint32_t source, uint32_t destination,
		unique_ptr<yamb_node::stream> msg)
{
	Document d;
	ParseResult ok = d.Parse((const char*) msg->pointer(), msg->remaining_length());

	if (!ok)
	{
		fprintf (stderr, "JSON parse error: %s (%lu)\n", GetParseError_En(ok.Code()), ok.Offset());
		return;
	}

	if (d.IsObject() && d.HasMember("identity") && d["identity"].IsString())
	{
		string identity = d["identity"].GetString();

		auto i = build_nodes.find(identity);

		bool node_list_changed = false;

		if (i == build_nodes.cend())
		{
			/* If we don't know about that node yet, add it. */
			build_nodes.insert({identity,
					move(make_shared<BuildNodeProxy::BuildNodeProxy>(*this,identity,source))});
			node_list_changed = true;
		}
		else
		{
			auto node = i->second;

			node->set_yamb_addr(source);
			node->message_received(d);
		}

		/* Call subscribers at the end to have the message fully interpreted. */
		if (node_list_changed)
			for_each(
					build_node_list_subscribers.begin(),
					build_node_list_subscribers.end(),
					[](BuildNodeListSubscriber &s){
						if (s.on_list_changed) {
							s.on_list_changed(s.priv);
						}
					});
	}
}

void BuildClusterProxy::build_master_message_received(
		yamb_node::yamb_node *nodes,
		uint32_t source, uint32_t destination,
		unique_ptr<yamb_node::stream> msg)
{
	Document d;
	ParseResult ok = d.Parse((const char*) msg->pointer(), msg->remaining_length());

	if (!ok)
	{
		fprintf (stderr, "JSON parse error: %s (%lu)\n", GetParseError_En(ok.Code()), ok.Offset());
		return;
	}

	if (d.IsObject() && d.HasMember("identity") && d["identity"].IsString())
	{
		string identity = d["identity"].GetString();

		auto i = build_masters.find(identity);

		bool master_list_changed = false;

		if (i == build_masters.cend())
		{
			/* If we don't know about that master yet, add it. */
			build_masters.insert(make_pair(identity,
					make_shared<BuildMasterProxy::BuildMasterProxy>(*this, identity, source)));

			master_list_changed = true;
		}
		else
		{
			auto master = i->second;

			master->set_yamb_addr(source);
			master->message_received(d);
		}

		/* Call subscribers at the end to have the message fully interpreted. */
		if (master_list_changed)
			for_each(
					build_master_list_subscribers.begin(),
					build_master_list_subscribers.end(),
					[](BuildMasterListSubscriber &s) {
						if (s.on_list_changed) {
							s.on_list_changed(s.priv);
						}
					});
	}
}


/**************************** Build node interface ****************************/
vector<string> BuildClusterProxy::list_build_nodes() const
{
	vector<string> v;

	for_each(build_nodes.cbegin(), build_nodes.cend(),
			[&v](pair<string,shared_ptr<BuildNodeProxy::BuildNodeProxy>> t) { v.push_back(t.first); });

	return v;
}

vector<shared_ptr<BuildNodeProxy::BuildNodeProxy>> BuildClusterProxy::get_build_nodes() const
{
	vector<shared_ptr<BuildNodeProxy::BuildNodeProxy>> v;

	for_each(build_nodes.cbegin(), build_nodes.cend(),
			[&v](pair<string,shared_ptr<BuildNodeProxy::BuildNodeProxy>> t) { v.push_back(t.second); });

	return v;
}

shared_ptr<BuildNodeProxy::BuildNodeProxy> BuildClusterProxy::get_build_node(string identity) const
{
	for (auto t : build_nodes)
		if (t.second->identity == identity)
			return t.second;

	return nullptr;
}

void BuildClusterProxy::subscribe_to_build_node_list(const BuildNodeListSubscriber &s)
{
	if (s.on_list_changed)
		build_node_list_subscribers.push_back(s);
}

void BuildClusterProxy::unsubscribe_from_build_node_list(void *priv)
{
	auto i = find(build_node_list_subscribers.begin(), build_node_list_subscribers.end(),
			BuildNodeListSubscriber(priv));

	if (i != build_node_list_subscribers.end())
		build_node_list_subscribers.erase(i);
}


/****************************** Build master interface ************************/
vector<string> BuildClusterProxy::list_build_masters() const
{
	vector<string> v;

	for_each(build_masters.cbegin(), build_masters.cend(),
			[&v](pair<string,shared_ptr<BuildMasterProxy::BuildMasterProxy>> t) { v.push_back(t.first); });

	return v;
}

shared_ptr<BuildMasterProxy::BuildMasterProxy> BuildClusterProxy::get_build_master(string identity) const
{
	auto i = build_masters.find(identity);

	if (i == build_masters.end())
		return nullptr;
	else
		return i->second;
}

void BuildClusterProxy::subscribe_to_build_master_list(const BuildMasterListSubscriber &s)
{
	if (s.on_list_changed)
		build_master_list_subscribers.push_back(s);
}

void BuildClusterProxy::unsubscribe_from_build_master_list(void* priv)
{
	auto i = find(build_master_list_subscribers.begin(), build_master_list_subscribers.end(),
			BuildMasterListSubscriber(priv));

	if (i != build_master_list_subscribers.end())
		build_master_list_subscribers.erase(i);
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

		build_nodes_last_searched = 0;
	}
}

void BuildClusterProxy::search_for_build_masters()
{
	if (ynode)
	{
		auto msg = make_unique<yamb_node::stream>();

		Document d;
		d.SetObject();
		d.AddMember("cmd", "identify", d.GetAllocator());

		StringBuffer buffer;
		Writer<StringBuffer> writer(buffer);
		d.Accept(writer);

		msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());

		build_master_yprotocol->send_message(ynode.get(), 0xffffffff, move(msg));

		build_masters_last_searched = 0;
	}
}


}
