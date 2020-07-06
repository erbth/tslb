#include <algorithm>
#include <rapidjson/error/en.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include "BuildMasterProxy.h"
#include "BuildClusterProxy.h"
#include "base64.h"
#include "utilities.h"

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

	/* Ignore messages from other clients */
	if (d.HasMember("cmd"))
		return;


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


	/* Console streaming */
	if (d.HasMember("console_streaming") && d["console_streaming"].IsObject())
	{
		const Value &cs = d["console_streaming"];

		if (cs.HasMember("msg") && cs["msg"].IsString())
		{
			string msg = cs["msg"].GetString();

			if (msg == "data" || msg == "update")
			{
				if (cs.HasMember("mdata") && cs["mdata"].IsArray() &&
						cs.HasMember("blob") && cs["blob"].IsString())
				{
					/* De-serialize array of tuples */
					const Value &mdata = cs["mdata"];

					vector<pair<uint32_t, uint32_t>> de_mdata(mdata.Size());

					bool failed = false;

					for (SizeType i = 0; i < mdata.Size(); i++)
					{
						const Value &t = mdata[i];

						if (t.IsArray() && t.Size() == 2 &&
								t[0].IsInt() && t[1].IsInt())
						{
							long int mark = t[0].GetInt();
							long int pointer = t[1].GetInt();

							if (mark < 0 || mark > 0xffffffff ||
									pointer < 0 || pointer > 0xffffffff)
							{
								failed = true;
								break;
							}

							de_mdata[i] = pair(mark, pointer);
						}
						else
						{
							failed = true;
							break;
						}
					}

					if (!failed)
					{
						/* Decode data blob */
						size_t blob_size;
						char *blob = base64_decode(
								cs["blob"].GetString(),
								cs["blob"].GetStringLength(),
								&blob_size);

						if (blob)
						{
							if (msg == "data")
								console_data_received(de_mdata, blob, blob_size);
							else
								console_update_received(de_mdata, blob, blob_size);
						}
					}
				}
			}
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


/* Swallows blob */
void BuildMasterProxy::console_data_received(
		vector<pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size)
{
	if (mdata.size() == 0)
		return;


	uint32_t first_mark = mdata.front().first;
	uint32_t last_mark = mdata.back().first;

	uint32_t min_mark_required = 0xffffffff;

	for (ConsoleSubscriber& sub : console_subscribers)
	{
		if (sub.last_mark_received == 0)
		{
			if (sub.new_data_cb)
				sub.new_data_cb(sub.priv, data, data_size);

			sub.last_mark_received = last_mark;
		}
		else
		{
			/* Is it acceptable and helpful? - And if not, what would be needed? */
			if (in_mark_range(mark_add_disp(first_mark, -1),
						mark_add_disp(last_mark, -1),
						sub.last_mark_received))
			{
				/* Calculate missing chunks from all we've got */
				const char *ptr = data;

				auto i = mdata.cbegin();
				while (in_mark_range(i->first, last_mark, sub.last_mark_received))
					ptr += (*i++).second;

				/* Call subscriber */
				if (sub.new_data_cb)
					sub.new_data_cb(sub.priv, ptr, data_size - (ptr - data));

				sub.last_mark_received = last_mark;
			}
			else if (last_mark != sub.last_mark_received)
			{
				/* This may request too much or not enough if wrap around
				 * occurs. However I'm not sure if the exact amount can be
				 * requested in every case ...
				 * Anyway, it should work within a few rounds once each single
				 * subscriber becomes synchronous one by one as the buffer at
				 * the sender is usually quite large. Otherwise the user has to
				 * refresh the console. (if it got stuck at a point from which
				 * no data is available. We could detect this but it would be
				 * more work and may require matchable requests and responses.
				 * The easier way would be using a receive buffer, which I'be
				 * been too lazy to do by now ...) */
				min_mark_required = min(min_mark_required, sub.last_mark_received);
			}
		}
	}

	/* Request missing chunks */
	if (min_mark_required < 0xffffffff)
		console_send_request(min_mark_required, 0xffffffff);

	free(data);
}

/* Swallows blob */
void BuildMasterProxy::console_update_received(
		vector<pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size)
{
	console_data_received(mdata, data, data_size);

	/* Send ack */
	if (console_subscribers.size() > 0)
		console_send_ack();
}

void BuildMasterProxy::console_send_request_updates()
{
	Document d;
	d.SetObject();

	Value cs(kObjectType);

	cs.AddMember("msg", "request_updates", d.GetAllocator());
	d.AddMember("console_streaming", cs, d.GetAllocator());

	send_message_to_master(d);
}

void BuildMasterProxy::console_send_ack()
{
	Document d;
	d.SetObject();

	Value cs(kObjectType);

	cs.AddMember("msg", "ack", d.GetAllocator());
	d.AddMember("console_streaming", cs, d.GetAllocator());

	send_message_to_master(d);
}

void BuildMasterProxy::console_send_request(uint32_t start, uint32_t end)
{
	Document d;
	d.SetObject();

	Value cs(kObjectType);

	cs.AddMember("msg", "request", d.GetAllocator());
	cs.AddMember("start", start, d.GetAllocator());
	cs.AddMember("end", end, d.GetAllocator());
	d.AddMember("console_streaming", cs, d.GetAllocator());

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


ConsoleSubscriber BuildMasterProxy::subscribe_to_console(
		ConsoleSubscriber::new_data_cb_t new_data_cb, void *priv)
{
	if (!priv)
		return ConsoleSubscriber();

	ConsoleSubscriber s(this, new_data_cb, priv);

	auto old = find(console_subscribers.begin(), console_subscribers.end(), s);

	if (old == console_subscribers.end())
		console_subscribers.push_back(s);
	else
		*old = s;

	/* Request updates on console buffer changes and request all old data */
	console_send_request_updates();
	console_send_request(0, 0xffffffff);

	return s;
}

void BuildMasterProxy::unsubscribe_from_console(ConsoleSubscriber &cs)
{
	auto i = find(console_subscribers.begin(), console_subscribers.end(), cs);

	if (i != console_subscribers.end())
	{
		console_subscribers.erase(i);

		/* The ConsoleSubscriber object should be unusable afterwards. */
		cs.priv = nullptr;
	}
}

void BuildMasterProxy::console_reconnect()
{
	for (ConsoleSubscriber &sub : console_subscribers)
		sub.last_mark_received = 0;

	console_send_request_updates();
	console_send_request(0, 0xffffffff);
}

}
