#include "BuildClusterWindow.h"
#include "ClientApplication.h"
#include "Message.h"
#include "stream.h"
#include <iostream>
#include <cstdio>

using namespace std;

static string yamb_addr_to_string(uint32_t addr)
{
	unsigned a = addr >> 24 & 0xff;
	unsigned b = addr >> 16 & 0xff;
	unsigned c = addr >> 8 & 0xff;
	unsigned d = addr& 0xff;

	char buf[12];
	sprintf(buf, "%02x:%02x:%02x:%02x", a, b, c, d);
	return string(buf);
}


ClusterOverview::ClusterOverview(BuildClusterWindow *bcwin) :
	Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	bcwin(bcwin)
{
	set_border_width(10);

	/* UI components */
	m_bBuild_master.pack_start (m_lBuild_master_description, false, false, 0);

	pack_start(m_bBuild_master, false, false, 0);
	m_bBuild_master.show();

	/* Initially update UI */
	update_build_master();
}

void ClusterOverview::update_build_master()
{
	if (bcwin->have_build_master)
	{
		m_lBuild_master_description.set_text(
				bcwin->build_master_id + " at yamb address " +
				yamb_addr_to_string(bcwin->build_master_yamb_addr));
	}
	else
	{
		m_lBuild_master_description.set_text("<none>");
	}
}



BuildClusterWindow::BuildClusterWindow(ClientApplication *c) :
	Gtk::Window(),
	m_client_application(c),
	have_build_master(false),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	m_lInfo("The TSClient LEGACY Build System."),
	m_cluster_overview(this)
{
	set_title ("The TSClient LEGACY Build System - Build cluster");
	set_border_width(10);
	input_stream = make_shared<stream>();

	/* UI components */
	m_nbMain.append_page(m_cluster_overview, "Overview");

	m_bMain_vbox.pack_start(m_lInfo, false, false, 0);
	m_bMain_vbox.pack_start(m_nbMain, true, true, 0);
	add(m_bMain_vbox);
	m_bMain_vbox.show_all();
}

BuildClusterWindow::~BuildClusterWindow()
{
	if (async_read_cancellable)
		async_read_cancellable->cancel();
}

void BuildClusterWindow::set_connection(Glib::RefPtr<Gio::SocketConnection> conn)
{
	if (this->conn != conn)
	{
		if (conn.get() == nullptr)
		{
			this->conn = conn;
		}
		else
		{
			this->conn = conn;

			/* Initialize the new connection by requesting stuff etc. */
			// Start the first read operation
			auto is = conn->get_input_stream();
			async_read_cancellable = Gio::Cancellable::create();
			is->read_async(
					read_buffer, 10000,
					sigc::mem_fun(*this, &BuildClusterWindow::async_read_ready),
					async_read_cancellable);

			request_build_master();
		}
	}
}

void BuildClusterWindow::async_read_ready(Glib::RefPtr<Gio::AsyncResult> async_result)
{
	ssize_t cnt_read;

	try {
		cnt_read = conn->get_input_stream()->read_finish(async_result);
		async_read_cancellable.reset();
	} catch (Glib::Error &e) {
		if (e.code() != G_IO_ERROR_CANCELLED)
		{
			cout << "Connection error: " << e.what() << endl;
			conn.reset();
			hide();
		}
		return;
	}

	if (cnt_read < 1)
	{
		cout << "Client proxy closed the connection." << endl;
		conn.reset();
		hide();
		return;
	}

	/* read_buffer, cnt_read is our input we got from the proxy */
	input_stream->write_data(read_buffer, cnt_read);

	auto l = Message::contains_full(*input_stream);
	if (l > 0)
	{
		auto msg = input_stream->pop(l);
		parse_message(msg);
	}

	/* Start a new read */
	async_read_cancellable = Gio::Cancellable::create();
	conn->get_input_stream()->read_async(
			read_buffer, 10000,
			sigc::mem_fun(*this, &BuildClusterWindow::async_read_ready),
			async_read_cancellable);
}

void BuildClusterWindow::parse_message(stream msg)
{
	auto msgid = msg.read_uint32();
	/* auto len = */msg.read_uint32();

	switch (msgid)
	{
		case 0x00100001:
			parse_build_master_update(msg);
			break;

		default:
			printf ("Received unknown message with msgid = %u.\n", (unsigned) msgid);
			break;
	};
}

void BuildClusterWindow::parse_build_master_update(stream msg)
{
	bool bm_changed;

	if (msg.remaining_length() > 0)
	{
		try {
			auto namelen = msg.read_uint32();
			auto name = msg.read_string(namelen);
			auto yamb_addr = msg.read_uint32();
			auto seems_dead = msg.read_uint8() > 0 ? true : false;

			bm_changed = !have_build_master || build_master_id != name;

			build_master_id = name;
			build_master_yamb_addr = yamb_addr;
			build_master_seems_dead = seems_dead;
			have_build_master = true;

		} catch (stream_no_data_error &e) {
			g_printerr("Received too short build_master_update.\n");
		}
	}
	else
	{
		bm_changed = have_build_master;
		have_build_master = false;
	}

	if (bm_changed)
		on_build_master_changed();
}

void BuildClusterWindow::request_build_master()
{
	if (conn)
	{
		auto s = Message::create_get_build_master();
		conn->get_output_stream()->write(s.c_str(), s.size());
	}
}

/* Logics functions */
void BuildClusterWindow::on_build_master_changed()
{
	/* Notify views */
	m_cluster_overview.update_build_master();
}
