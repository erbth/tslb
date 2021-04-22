#include "ConnectingWindow.h"
#include "BuildClusterProxy.h"
#include "ClientApplication.h"

using namespace std;

ConnectingWindow::ConnectingWindow (ClientApplication *c) :
	Gtk::Window (),
	m_client_application(c),
	m_build_cluster_proxy(c->get_build_cluster_proxy()),
	m_lInfo ("Intializing"),
	m_btAbort("Abort"),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL)
{
	set_default_size (300, 200);
	set_border_width (10);
	set_title ("Connecting to the yamb hub");
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
	signal_key_press_event().connect(sigc::mem_fun(*this, &ConnectingWindow::on_window_key_press));

	m_build_cluster_proxy.subscribe_to_connection_state(
			BuildClusterProxy::ConnectionStateSubscriber(
				&ConnectingWindow::_connection_established,
				nullptr,
				&ConnectingWindow::_connection_failed,
				this));
}

ConnectingWindow::~ConnectingWindow()
{
	m_build_cluster_proxy.unsubscribe_from_connection_state(this);
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

bool ConnectingWindow::on_window_key_press(GdkEventKey *event)
{
	if (event->keyval == GDK_KEY_Escape)
	{
		abort();
		return true;
	}
	return false;
}

void ConnectingWindow::abort()
{
	hide();
}


void ConnectingWindow::connection_established()
{
	m_client_application->connected();
	hide();
}

void ConnectingWindow::connection_failed(string error)
{
	m_client_application->failed_to_connect(error);
	hide();
}

void ConnectingWindow::_connection_established(void *pThis)
{
	((ConnectingWindow*)pThis)->connection_established();
}

void ConnectingWindow::_connection_failed(void *pThis, string error)
{
	((ConnectingWindow*)pThis)->connection_failed(error);
}


void ConnectingWindow::connect()
{
	auto addr = m_client_application->get_yamb_hub_addr();

	// Start to connect to yamb
	m_lInfo.set_text("Connecting to yamb hub on " + addr + " ...");
	auto ret = m_build_cluster_proxy.connect_to_hub(addr);

	if (ret)
	{
		m_client_application->failed_to_connect(ret.value());
		hide();
	}
}
