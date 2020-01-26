#include <algorithm>
#include <cstdio>
#include <memory>
#include <rapidjson/error/en.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <yamb_node++.hpp>
#include "BuildNodeProxy.h"
#include "BuildClusterProxy.h"

using namespace std;
using namespace rapidjson;

namespace BuildNodeProxy
{

BuildNodeProxy::BuildNodeProxy(
		BuildClusterProxy::BuildClusterProxy &bcp,
		string identity,
		uint32_t yamb_addr)
	:
		identity(identity), build_cluster_proxy(bcp), current_yamb_address(yamb_addr)
{
	query_state();
}

void BuildNodeProxy::query_state()
{
	Document d;
	d.SetObject();

	d.AddMember("action", "get_status", d.GetAllocator());

	StringBuffer buffer;
	Writer<StringBuffer> writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_node_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}


void BuildNodeProxy::timeout_1s()
{
	auto was_responding = is_responding();

	if (++last_state_update > 20)
		query_state();

	/* Responding behavior changed? */
	auto r = is_responding();

	if (was_responding != r)
	{
		/* If yes, inform subscribers. */
		for_each(state_subscribers.cbegin(), state_subscribers.cend(),
				[r](const StateSubscriber &s){
					if (s.on_responding_changed)
						s.on_responding_changed(s.priv, r);
				});
	}
}

void BuildNodeProxy::set_yamb_addr(uint32_t addr)
{
	if (addr != current_yamb_address)
	{
		current_yamb_address = addr;

		/* The node may have been restarted */
		query_state();
	}
}

void BuildNodeProxy::message_received(rapidjson::Document &d)
{
	if (d.HasMember("state") && d["state"].IsString())
	{
		auto was_responding = is_responding();

		string _new_state = d["state"].GetString();
		enum State new_state;
		last_state_update = 0;

		if (_new_state == "idle")
		{
			new_state = STATE_IDLE;
		}
		else if (_new_state == "building")
		{
			new_state = STATE_BUILDING;
		}
		else if (_new_state == "finished")
		{
			new_state = STATE_FINISHED;
		}
		else if (_new_state == "failed")
		{
			new_state = STATE_FAILED;
		}
		else if (_new_state == "maintenance")
		{
			new_state = STATE_MAINTENANCE;
		}
		else
		{
			fprintf (stderr, "Invalid state `%s' in update from build node %s.\n",
					_new_state.c_str(), identity.c_str());
			return;
		}

		bool state_changed = false;

		if (new_state != state)
		{
			state = new_state;
			state_changed = true;
		}

		/* Extended state */
		string tmp;

		if (d.HasMember("name") && d["name"].IsString())
		{
			tmp = d["name"].GetString();

			if (tmp != pkg_name)
			{
				pkg_name = tmp;
				state_changed = true;
			}
		}

		if (d.HasMember("arch") && d["arch"].IsString())
		{
			tmp = d["arch"].GetString();

			if (tmp != pkg_arch)
			{
				pkg_arch = tmp;
				state_changed = true;
			}
		}

		if (d.HasMember("version") && d["version"].IsString())
		{
			tmp = d["version"].GetString();

			if (tmp != pkg_version)
			{
				pkg_version = tmp;
				state_changed = true;
			}
		}

		if (d.HasMember("reason") && d["reason"].IsString())
		{
			tmp = d["reason"].GetString();

			if (tmp != fail_reason)
			{
				fail_reason = tmp;
				state_changed = true;
			}
		}

		/* Inform subscribers about changes in responsiveness */
		if (!was_responding)
		{
			for_each(state_subscribers.cbegin(), state_subscribers.cend(),
					[](const StateSubscriber &s) {
						if (s.on_responding_changed)
							s.on_responding_changed(s.priv, true);
					});
		}

		if (state_changed)
		{
			/* Inform subscribers */
			auto _state = state;

			for_each(state_subscribers.cbegin(), state_subscribers.cend(),
					[_state](const StateSubscriber &s)
					{
						if (s.on_state_changed)
							s.on_state_changed(s.priv, _state);
					});
		}
	}

	if (d.HasMember("err") && d["err"].IsString())
	{
		string err = d["err"].GetString();

		for_each(state_subscribers.cbegin(), state_subscribers.cend(),
				[err](const StateSubscriber &s){
					if (s.on_error_received)
						s.on_error_received(s.priv, err);
				});
	}
}

bool BuildNodeProxy::is_responding() const
{
	return last_state_update < 30;
}

enum State BuildNodeProxy::get_state() const
{
	return state;
}

string BuildNodeProxy::get_pkg_name() const
{
	return pkg_name;
}

string BuildNodeProxy::get_pkg_arch() const
{
	return pkg_arch;
}

string BuildNodeProxy::get_pkg_version() const
{
	return pkg_version;
}

string BuildNodeProxy::get_fail_reason() const
{
	return fail_reason;
}


/* Objects can subscribe to the build node's (proxy's) state. */
void BuildNodeProxy::subscribe_to_state(const StateSubscriber &s)
{
	if (s.on_responding_changed || s.on_state_changed || s.on_error_received)
		state_subscribers.push_back(s);
}

void BuildNodeProxy::unsubscribe_from_state(void *priv)
{
	auto i = find(state_subscribers.begin(), state_subscribers.end(),
			StateSubscriber(priv));

	if (i != state_subscribers.end())
		state_subscribers.erase(i);
}


/* More actions */
void BuildNodeProxy::request_start_build(string name, string arch, string version)
{
	Document d;
	d.SetObject();

	d.AddMember("action", "start_build", d.GetAllocator());
	d.AddMember("name", StringRef(name.c_str()), d.GetAllocator());
	d.AddMember("arch", StringRef(arch.c_str()), d.GetAllocator());
	d.AddMember("version", StringRef(version.c_str()), d.GetAllocator());

	StringBuffer buffer;
	Writer<StringBuffer> writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_node_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}

void BuildNodeProxy::request_abort_build()
{
	Document d;
	d.SetObject();

	d.AddMember("action", "abort_build", d.GetAllocator());

	StringBuffer buffer;
	Writer<StringBuffer> writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_node_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}

void BuildNodeProxy::request_reset()
{
	Document d;
	d.SetObject();

	d.AddMember("action", "reset", d.GetAllocator());

	StringBuffer buffer;
	Writer<StringBuffer> writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_node_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}

void BuildNodeProxy::request_enable_maintenance()
{
	Document d;
	d.SetObject();

	d.AddMember("action", "enable_maintenance", d.GetAllocator());

	StringBuffer buffer;
	Writer<StringBuffer> writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_node_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}

void BuildNodeProxy::request_disable_maintenance()
{
	Document d;
	d.SetObject();

	d.AddMember("action", "disable_maintenance", d.GetAllocator());

	StringBuffer buffer;
	Writer<StringBuffer> writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_node_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}

}
