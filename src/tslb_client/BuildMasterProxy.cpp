#include <algorithm>
#include <rapidjson/error/en.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include "BuildMasterProxy.h"
#include "BuildClusterProxy.h"

using namespace std;
using namespace rapidjson;

namespace BuildMasterProxy
{

BuildMasterProxy::BuildMasterProxy(
		BuildClusterProxy::BuildClusterProxy &bcp,
		string identity,
		uint32_t yamb_addr)
	:
		identity(identity),
		build_cluster_proxy(bcp),
		current_yamb_address(yamb_addr)
{
	refresh();
}


void BuildMasterProxy::timeout_1s()
{
	auto was_responding = is_responding();

	++last_response;

	if (++last_refresh_sent > 10)
	{
		refresh();
	}

	/* Responding behavior changed? */
	auto r = is_responding();

	if (was_responding != r)
	{
		/* If yes, inform subscribers. */
		for_each(subscribers.cbegin(), subscribers.cend(),
				[r](const Subscriber s) {
					if (s.on_responding_changed)
						s.on_responding_changed(s.priv);
					});
	}
}


void BuildMasterProxy::set_yamb_addr(uint32_t addr)
{
	if (addr != current_yamb_address)
	{
		current_yamb_address = addr;

		/* The master may have been restarted */
		refresh();
	}
}


void BuildMasterProxy::message_received(rapidjson::Document& d)
{
	auto was_responding = is_responding();

	last_response = 0;

	/* Different flags for the notifications */
	bool remaining_changed = false;
	bool build_queue_changed = false;
	bool building_set_changed = false;
	bool nodes_changed = false;
	bool state_changed = false;


	/* Remaining packages */
	if (d.HasMember("remaining") && d["remaining"].IsArray())
	{
		auto old_remaining = move(remaining);

		for (auto &v : d["remaining"].GetArray())
		{
			if (!v.IsArray() || v.Capacity() != 2 || !v[0].IsString() || !v[1].IsString())
			{
				fprintf (stderr, "BM: recv: remaining has an element of invalid type.\n");
				continue;
			}

			string pkg_name = v[0].GetString();
			string pkg_version = v[1].GetString();

			remaining.insert(make_pair(pkg_name, pkg_version));
		}

		remaining_changed = remaining != old_remaining;
	}


	/* Build queue */
	if (d.HasMember("build-queue") && d["build-queue"].IsArray())
	{
		auto old_build_queue = move(build_queue);

		for (auto &v : d["build-queue"].GetArray())
		{
			if (!v.IsArray() || v.Capacity() != 2 || !v[0].IsString() || !v[1].IsString())
			{
				fprintf (stderr, "BM: recv: build-queue has an element of invalid type.\n");
				continue;
			}

			string pkg_name = v[0].GetString();
			string pkg_version = v[1].GetString();

			build_queue.push_back(make_pair(pkg_name, pkg_version));
		}

		build_queue_changed = build_queue != old_build_queue;
	}


	/* Building set */
	if (d.HasMember("building-set") && d["building-set"].IsArray())
	{
		auto old_building_set = move(building_set);

		for (auto &v : d["building-set"].GetArray())
		{
			if (!v.IsArray() || v.Capacity() != 2 || !v[0].IsString() || !v[1].IsString())
			{
				fprintf (stderr, "BM: recv: building-set has an element of invalid type.\n");
				continue;
			}

			string pkg_name = v[0].GetString();
			string pkg_version = v[1].GetString();

			building_set.insert(make_pair(pkg_name, pkg_version));
		}

		building_set_changed = old_building_set != building_set;
	}


	/* Build nodes */
	if (d.HasMember("idle-nodes") && d["idle-nodes"].IsArray())
	{
		auto old_idle_nodes = move(idle_nodes);

		for (auto &v : d["idle-nodes"].GetArray())
		{
			if (!v.IsString())
			{
				fprintf (stderr, "BM: recv: idle-nodes has an element of invalid type.\n");
				continue;
			}

			idle_nodes.push_back(v.GetString());
		}

		nodes_changed |= old_idle_nodes != idle_nodes;
	}

	if (d.HasMember("busy-nodes") && d["busy-nodes"].IsArray())
	{
		auto old_busy_nodes = move(busy_nodes);

		for (auto &v : d["busy-nodes"].GetArray())
		{
			if (!v.IsString())
			{
				fprintf (stderr, "BM: recv: busy-nodes has an element of invalid type.\n");
				continue;
			}

			busy_nodes.push_back(v.GetString());
		}

		nodes_changed |= old_busy_nodes != busy_nodes;
	}


	/* State */
	if (d.HasMember("state") && d["state"].IsString())
	{
		string new_state_str = d["state"].GetString();
		enum state new_state = BMP_STATE_INVALID;

		if (new_state_str == "off")
			new_state = BMP_STATE_OFF;
		else if (new_state_str == "idle")
			new_state = BMP_STATE_IDLE;
		else if (new_state_str == "computing")
			new_state = BMP_STATE_COMPUTING;
		else if (new_state_str == "building")
			new_state = BMP_STATE_BUILDING;

		if (new_state == BMP_STATE_INVALID)
		{
			fprintf (stderr, "Received invalid build master state: `%s'.\n",
					new_state_str.c_str());
		}
		else if (new_state != state)
		{
			state = new_state;
			state_changed = true;
		}
	}

	if (d.HasMember("arch") && d["arch"].IsString())
	{
		string new_arch_str = d["arch"].GetString();
		enum architecture new_arch = ARCH_INVALID;

		if (new_arch_str == "i386")
			new_arch = ARCH_I386;
		else if (new_arch_str == "amd64")
			new_arch = ARCH_AMD64;

		if (new_arch == ARCH_INVALID)
		{
			fprintf (stderr,
					"Received invalid architecture from build master: `%s'.\n",
					new_arch_str.c_str());
		}
		else if (new_arch != architecture)
		{
			architecture = new_arch;
			state_changed = true;
		}
	}

	if (d.HasMember("error") && d["error"].IsBool())
	{
		bool new_error = d["error"].GetBool();
		if (new_error != error)
		{
			error = new_error;
			state_changed = true;
		}
	}

	if (d.HasMember("valve") && d["valve"].IsBool())
	{
		bool new_valve = d["valve"].GetBool();
		if (new_valve != valve)
		{
			valve = new_valve;
			state_changed = true;
		}
	}


	/* Responding behavior changed? */
	bool responding_changed = was_responding == is_responding();


	/* Notify subscribers about changed state */
	for_each(subscribers.cbegin(), subscribers.cend(),
		[=](const Subscriber &s) {
			if (responding_changed && s.on_responding_changed) {
				s.on_responding_changed(s.priv);
			}
			if (remaining_changed && s.on_remaining_changed) {
				s.on_remaining_changed(s.priv);
			}
			if (build_queue_changed && s.on_build_queue_changed) {
				s.on_build_queue_changed(s.priv);
			}
			if (building_set_changed && s.on_building_set_changed) {
				s.on_building_set_changed(s.priv);
			}
			if (nodes_changed && s.on_nodes_changed) {
				s.on_nodes_changed(s.priv);
			}
			if (state_changed && s.on_state_changed) {
				s.on_state_changed(s.priv);
			}
		});


	/* Error message */
	if (d.HasMember("error") && d["error"].IsString())
	{
		string error = d["error"].GetString();

		for (const auto &subs : subscribers)
		{
			if (subs.on_error_received)
				subs.on_error_received(subs.priv, error);
		}
	}
}


void BuildMasterProxy::send_message_to_master(rapidjson::Document& d)
{
	d.AddMember("identity", StringRef(identity.c_str(), identity.size()),
			d.GetAllocator());

	StringBuffer buffer;
	Writer writer(buffer);
	d.Accept(writer);

	auto msg = make_unique<yamb_node::stream>();
	msg->write_data((uint8_t*) buffer.GetString(), buffer.GetSize());
	build_cluster_proxy.build_master_yprotocol->send_message(
			build_cluster_proxy.ynode.get(),
			current_yamb_address,
			move(msg));
}

void BuildMasterProxy::send_get_state()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "get-state", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::send_get_remaining()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "get-remaining", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::send_get_build_queue()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "get-build-queue", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::send_get_building_set()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "get-building-set", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::send_get_nodes()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "get-nodes", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::send_subscribe()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "subscribe", d.GetAllocator());
	send_message_to_master(d);
}


/****************************** Querying state ********************************/
bool BuildMasterProxy::is_responding() const
{
	return last_response < 13;
}

const set<pair<string, string>> &BuildMasterProxy::get_remaining() const
{
	return remaining;
}

const vector<pair<string, string>> &BuildMasterProxy::get_build_queue() const
{
	return build_queue;
}

const set<pair<string, string>> &BuildMasterProxy::get_building_set() const
{
	return building_set;
}

const vector<string> &BuildMasterProxy::get_idle_nodes() const
{
	return idle_nodes;
}

const vector<string> &BuildMasterProxy::get_busy_nodes() const
{
	return busy_nodes;
}

enum state BuildMasterProxy::get_state() const
{
	return state;
}

enum architecture BuildMasterProxy::get_architecture() const
{
	return architecture;
}

bool BuildMasterProxy::get_error() const
{
	return error;
}

bool BuildMasterProxy::get_valve() const
{
	return valve;
}


void BuildMasterProxy::subscribe(const Subscriber &s)
{
	if (find(subscribers.cbegin(), subscribers.cend(), s) == subscribers.cend())
	{
		subscribers.push_back(s);

		/* If this is the first subscriber, subscribe to the build master's
		 * state via yamb and request a status update. */
		if (subscribers.size() == 1)
		{
			refresh();
		}
	}
}

void BuildMasterProxy::unsubscribe(void *priv)
{
	auto i = find(subscribers.begin(), subscribers.end(), Subscriber(priv));
	if (i != subscribers.cend())
		subscribers.erase(i);
}


/**
 * If the build master has subscribers, this method requests updates for the
 * entire state of the build master including e.g. the build queue and
 * subscribers to it. If it does not have subscribers, it only sends an
 * "identify"-message to see if the master is still active. */
void BuildMasterProxy::refresh()
{
	last_refresh_sent = 0;

	if (subscribers.size() > 0)
	{
		send_subscribe();
		send_get_state();
		send_get_remaining();
		send_get_build_queue();
		send_get_building_set();
		send_get_nodes();
	}
	else
	{
		Document d;
		d.SetObject();

		d.AddMember("cmd", "identify", d.GetAllocator());
		send_message_to_master(d);
	}
}

void BuildMasterProxy::start(enum architecture arch)
{
	Document d;
	d.SetObject();

	const char *arch_str;

	switch (arch)
	{
		case ARCH_I386:
			arch_str = "i386";
			break;

		case ARCH_AMD64:
			arch_str = "amd64";
			break;

		default:
			throw gp_exception("Invalid architecture: " + to_string(arch));
	}

	d.AddMember("cmd", "start", d.GetAllocator());
	d.AddMember("arch", Value().SetString(arch_str, d.GetAllocator()), d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::stop()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "stop", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::open()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "open", d.GetAllocator());
	send_message_to_master(d);
}

void BuildMasterProxy::close()
{
	Document d;
	d.SetObject();

	d.AddMember("cmd", "close", d.GetAllocator());
	send_message_to_master(d);
}

}
