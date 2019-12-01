#include "ConnectingWindow.h"
#include "ClientApplication.h"

using namespace std;

ConnectingWindow::ConnectingWindow (ClientApplication *c, string host) :
	Gtk::Window (),
	m_client_application(c),
	m_lInfo ("Intializing"),
	m_btAbort("Abort"),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL)
{
	set_default_size (300, 200);
	set_border_width (10);
	set_title ("Connecting to TSClient LEGACY Build System");
	set_type_hint (Gdk::WindowTypeHint::WINDOW_TYPE_HINT_SPLASHSCREEN);

	override_background_color (Gdk::RGBA("#008000"));

	// Layout
	m_blInfo.pack_start(m_lInfo, true, true, 0);
	m_bAbort.pack_end(m_btAbort, false, false, 0);

	m_bMain_vbox.pack_start(m_blInfo, true, true, 0);
	m_bMain_vbox.pack_end(m_bAbort, false, false, 0);

	add(m_bMain_vbox);

	m_bMain_vbox.show_all();

	// Connect signal handlers
	m_btAbort.signal_clicked().connect(sigc::mem_fun(*this, &ConnectingWindow::btAbort_clicked));
	signal_delete_event().connect(sigc::mem_fun(*this, &ConnectingWindow::on_window_delete));

	// Start to connect
	m_socket_client = Gio::SocketClient::create();

	m_lInfo.set_text("Connecting to " + host + " ...");

	m_connect_cancellable = Gio::Cancellable::create();
	m_socket_client->connect_to_host_async (host, 30100, m_connect_cancellable,
			sigc::mem_fun(*this, &ConnectingWindow::async_connect_ready));
}

void ConnectingWindow::btAbort_clicked()
{
	abort();
}

bool ConnectingWindow::on_window_delete(GdkEventAny *any_event)
{
	abort();
	return true;
}

void ConnectingWindow::abort()
{
	if (m_connect_cancellable)
		m_connect_cancellable->cancel();

	hide();
}

void ConnectingWindow::async_connect_ready (Glib::RefPtr<Gio::AsyncResult> async_result)
{
	Glib::RefPtr<Gio::SocketConnection> conn;

	try {
		conn = m_socket_client->connect_to_host_finish(async_result);
	} catch (Glib::Error &e) {
		m_client_application->failed_to_connect(e.what());
		hide();
		return;
	}

	if (conn)
		m_client_application->connected(conn);

	hide();
}
