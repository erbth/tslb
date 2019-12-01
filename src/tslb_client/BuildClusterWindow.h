#ifndef __BUILD_CLUSTER_WINDOW_H
#define __BUILD_CLUSTER_WINDOW_H

#include <gtkmm.h>

/* Prototypes */
class ClientApplication;

class BuildClusterWindow : public Gtk::Window
{
protected:
	ClientApplication *m_client_application;
	Glib::RefPtr<Gio::SocketConnection> conn;

public:
	BuildClusterWindow(ClientApplication *c);

	void set_connection(Glib::RefPtr<Gio::SocketConnection> conn);

	void request_build_master();
};

#endif
