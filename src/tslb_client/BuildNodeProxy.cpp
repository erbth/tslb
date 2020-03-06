#include <algorithm>
#include <cstdio>
#include <memory>
#include <rapidjson/error/en.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <yamb_node++.hpp>
#include "BuildNodeProxy.h"
#include "BuildClusterProxy.h"
#include "base64.h"
#include "utilities.h"

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
							long int pointer = t[0].GetInt();

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


/* Swallows blob */
void BuildNodeProxy::console_data_received(
		vector<pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size)
{
	if (mdata.size() == 0)
		return;


	uint32_t first_mark = mdata.front().first;
	uint32_t last_mark = mdata.back().second;

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
			else
			{
				/* This may request too much or not enough if wrap around
				 * occurs. However I'm not sure if the exact amount can be
				 * requested in every case ...
				 * Anyway, it should work withing a few rounds once each single
				 * subscriber becomes synchronous one bye one as the buffer at
				 * the sender is usually quite large. Otherwise the user has to
				 * close and reopen the console. (if it got stuck at a point
				 * from which no data is available. we could detect this but it
				 * would be more work and may require matchable requests and
				 * responses. The easier way would be using a receive buffer,
				 * which I've been too lazy to do by now ...) */
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
void BuildNodeProxy::console_update_received(
		vector<pair<uint32_t, uint32_t>> mdata, char *data, size_t data_size)
{
	console_data_received(mdata, data, data_size);

	/* Send ack */
	console_send_ack();
}

void BuildNodeProxy::console_send_request_updates()
{
	Document d;
	d.SetObject();

	Value cs(kObjectType);

	cs.AddMember("msg", "request_updates", d.GetAllocator());
	d.AddMember("console_streaming", cs, d.GetAllocator());

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

void BuildNodeProxy::console_send_ack()
{
	Document d;
	d.SetObject();

	Value cs(kObjectType);

	cs.AddMember("msg", "ack", d.GetAllocator());
	d.AddMember("console_streaming", cs, d.GetAllocator());

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

void BuildNodeProxy::console_send_request(uint32_t start, uint32_t end)
{
	Document d;
	d.SetObject();

	Value cs(kObjectType);

	cs.AddMember("msg", "request", d.GetAllocator());
	cs.AddMember("start", start, d.GetAllocator());
	cs.AddMember("end", end, d.GetAllocator());
	d.AddMember("console_streaming", cs, d.GetAllocator());

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


ConsoleSubscriber BuildNodeProxy::subscribe_to_console(
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

void BuildNodeProxy::unsubscribe_from_console(ConsoleSubscriber &cs)
{
	auto i = find(console_subscribers.begin(), console_subscribers.end(), cs);

	if (i != console_subscribers.end())
	{
		console_subscribers.erase(i);

		/* The ConsoleSubscribere object should be unusable afterwards. */
		cs.priv = nullptr;
	}
}

}
