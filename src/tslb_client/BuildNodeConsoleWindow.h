#ifndef __BUILD_NODE_CONSOLE_WINDOW_H
#define __BUILD_NODE_CONSOLE_WINDOW_H

#include <gtkmm.h>
#include <vte/vte.h>
#include <memory>
#include "BuildNodeProxy.h"

class BuildNodeConsoleWindow : public Gtk::Window
{
private:
	std::shared_ptr<BuildNodeProxy::BuildNodeProxy> node;

	/* UI components */
	Gtk::Box m_bMain_vbox;
	Gtk::Label m_lInfo;

	/* This is old school. */
	GtkWidget *m_vteTerminal = nullptr;

	BuildNodeProxy::ConsoleSubscriber cs;

	/* Console data receiving callbacks */
	static void _new_console_data(void* priv, const char* data, size_t size);
	void new_console_data(const char* data, size_t size);

public:
	BuildNodeConsoleWindow(std::shared_ptr<BuildNodeProxy::BuildNodeProxy>);
	virtual ~BuildNodeConsoleWindow();
};

#endif /* __BUILD_NODE_CONSOLE_WINDOW_H */
