#include "ConnectDialog.h"

using namespace std;

ConnectDialog::ConnectDialog() :
	Gtk::Window(),
	m_lDescription("Welcome to the client for TSClient LEGACY Build System."
			"Connect to a Client Proxy in a build cluster."),
	m_leProxy("Hostname or IP-Address of Client Proxy:"),
	m_btConnect("Connect"),
	m_btAbort("Abort"),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL)
{
	set_default_size (300, 200);
	set_title ("Connect to the TSClient LEGACY Build System");
	set_type_hint (Gdk::WindowTypeHint::WINDOW_TYPE_HINT_DIALOG);

	// Layout
	m_bBt_box.pack_start (m_btConnect);
	m_bBt_box.pack_end (m_btAbort);

	m_bMain_vbox.pack_start(m_lDescription, false, false, 0);
	m_bMain_vbox.pack_start(m_leProxy, false, false, 0);
	m_bMain_vbox.pack_start(m_eProxy, false, false, 0);
	m_bMain_vbox.pack_start(m_bBt_box, false, false, 0);

	add(m_bMain_vbox);
	m_bMain_vbox.show_all();
}
