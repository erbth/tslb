#include "BuildNodeConsoleWindow.h"

using namespace std;
using namespace BuildNodeProxy;


BuildNodeConsoleWindow::BuildNodeConsoleWindow(
		shared_ptr<BuildNodeProxy::BuildNodeProxy> node)
	:
		Gtk::Window(),
		m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10)
{
	this->node = node;

	set_border_width (10);
	set_title("Console on Build Node: " + node->identity);

	m_lInfo.set_markup("Console on Build Node: " + node->identity);

	/* UI components */
	m_bMain_vbox.pack_start(m_lInfo, false, false, 0);

	m_vteTerminal = vte_terminal_new();
	gtk_box_pack_start(GTK_BOX(m_bMain_vbox.gobj()), m_vteTerminal, true, true, 0);

	add(m_bMain_vbox);

	m_bMain_vbox.show_all();

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
