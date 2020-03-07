#include "BuildNodeConsoleWindow.h"

using namespace std;
using namespace BuildNodeProxy;


BuildNodeConsoleWindow::BuildNodeConsoleWindow(
		shared_ptr<BuildNodeProxy::BuildNodeProxy> node)
	:
		Gtk::Window(),
		m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
		m_bTerminal(Gtk::Orientation::ORIENTATION_HORIZONTAL, 2),
		m_bHeader(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
		m_btReconnect("reconnect")
{
	this->node = node;

	set_border_width (10);
	set_title("Console on Build Node: " + node->identity);

	m_lInfo.set_markup("Console on Build Node: " + node->identity);

	/* UI components */
	m_bHeader.pack_start(m_lInfo, true, true, 0);
	m_bHeader.pack_start(m_btReconnect, false, false, 0);
	m_bMain_vbox.pack_start(m_bHeader, false, false, 0);

	/* The terminal and its scrollbar */
	m_vteTerminal = vte_terminal_new();
	vte_terminal_set_cursor_blink_mode(VTE_TERMINAL(m_vteTerminal),
			VTE_CURSOR_BLINK_OFF);

	vte_terminal_set_scrollback_lines(VTE_TERMINAL(m_vteTerminal), 100000);
	vte_terminal_set_size(VTE_TERMINAL(m_vteTerminal), 80, 25);

	gtk_box_pack_start(GTK_BOX(m_bTerminal.gobj()), m_vteTerminal, true, true, 0);

	m_sTerminal = gtk_scrollbar_new(GTK_ORIENTATION_VERTICAL,
			gtk_scrollable_get_vadjustment(GTK_SCROLLABLE(m_vteTerminal)));

	gtk_box_pack_start(GTK_BOX(m_bTerminal.gobj()), m_sTerminal, false, false, 0);

	m_bMain_vbox.pack_start(m_bTerminal, true, true, 0);
	add(m_bMain_vbox);

	m_bMain_vbox.show_all();

	/* Connect signal handlers */
	m_btReconnect.signal_clicked().connect(sigc::mem_fun(
				*this, &BuildNodeConsoleWindow::on_reconnect_clicked));

	g_signal_connect(G_OBJECT(m_vteTerminal), "commit",
			G_CALLBACK(BuildNodeConsoleWindow::_on_terminal_commit),
			this);

	/* Subscribe to console output */
	cs = node->subscribe_to_console(_new_console_data, this);
}

BuildNodeConsoleWindow::~BuildNodeConsoleWindow()
{
	node->unsubscribe_from_console(cs);
}


void BuildNodeConsoleWindow::_new_console_data(void *priv, const char *data, size_t size)
{
	((BuildNodeConsoleWindow*) priv)->new_console_data(data, size);
}

void BuildNodeConsoleWindow::new_console_data(const char *data, size_t size)
{
	vte_terminal_feed(VTE_TERMINAL(m_vteTerminal), data, size);
}


void BuildNodeConsoleWindow::_on_terminal_commit(VteTerminal *terminal, gchar *text, guint size, gpointer priv)
{
	((BuildNodeConsoleWindow*) priv)->on_terminal_commit(text, size);
}

void BuildNodeConsoleWindow::on_terminal_commit(const char *text, size_t size)
{
	node->console_send_input(text, size);
}

void BuildNodeConsoleWindow::on_reconnect_clicked()
{
	vte_terminal_reset(VTE_TERMINAL(m_vteTerminal), TRUE, TRUE);
	node->console_reconnect();
}
