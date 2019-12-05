#include "ConnectDialog.h"
#include "ClientApplication.h"

using namespace std;

ConnectDialog::ConnectDialog(ClientApplication *c) :
	Gtk::Window(),
	client_application(c),
	m_lDescription("Welcome to the client for TSClient LEGACY Build System."
			" Connect to a Client Proxy in a build cluster."),
	m_leProxy("Hostname or IP-Address of Client Proxy:"),
	m_btConnect("Connect"),
	m_btAbort("Abort"),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	m_eProxy_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 2)
{
	set_default_size (300, 200);
	set_border_width (10);
	set_title ("Connect to TSClient LEGACY Build System");
	set_type_hint (Gdk::WindowTypeHint::WINDOW_TYPE_HINT_DIALOG);

	m_lDescription.set_line_wrap(true);

	// Layout
	m_bBt_box.pack_start (m_btConnect);
	m_bBt_box.pack_end (m_btAbort);

	m_bleProxy.pack_start(m_leProxy, false, false, 0);
	m_eProxy_vbox.pack_start(m_bleProxy, false, false, 0);
	m_eProxy_vbox.pack_start(m_eProxy, false, false, 0);

	m_bMain_vbox.pack_start(m_lDescription, false, false, 0);
	m_bMain_vbox.pack_end(m_bBt_box, false, false, 0);
	m_bMain_vbox.pack_end(m_eProxy_vbox, false, false, 0);

	add(m_bMain_vbox);
	m_bMain_vbox.show_all();

	// Connect signal handlers
	m_btAbort.signal_clicked().connect(sigc::mem_fun(*this, &ConnectDialog::btAbort_clicked));
	m_btConnect.signal_clicked().connect(sigc::mem_fun(*this, &ConnectDialog::btConnect_clicked));
	m_eProxy.signal_activate().connect(sigc::mem_fun(*this, &ConnectDialog::eProxy_activate));
	signal_key_press_event().connect(sigc::mem_fun(*this, &ConnectDialog::on_window_key_press));
}

void ConnectDialog::btAbort_clicked()
{
	abort();
}

void ConnectDialog::btConnect_clicked()
{
	connect(m_eProxy.get_text());
}

void ConnectDialog::eProxy_activate()
{
	connect(m_eProxy.get_text());
}

bool ConnectDialog::on_window_key_press(GdkEventKey *event)
{
	switch (event->keyval)
	{
		case GDK_KEY_Escape:
		{
			abort();
			return true;
		}

		default:
			return false;
	}
}

void ConnectDialog::abort()
{
	hide();
}

void ConnectDialog::connect(string hostname)
{
	client_application->connect (hostname);
	hide();
}
