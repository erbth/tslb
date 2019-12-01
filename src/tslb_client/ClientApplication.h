#ifndef __CLIENT_APPLICATION_H
#define __CLIENT_APPLICATION_H

#include <gtkmm.h>
#include <memory>

/* Prototypes */
class ConnectDialog;
class ConnectingWindow;
class BuildClusterWindow;

class ClientApplication : public Gtk::Application
{
private:
	std::shared_ptr<ConnectDialog> connect_dialog;
	std::shared_ptr<ConnectingWindow> connecting_window;
	std::shared_ptr<Gtk::MessageDialog> connection_failure_dialog;
	std::shared_ptr<BuildClusterWindow> build_cluster_window;

	ClientApplication ();

	void on_activate ();

	/* Functions that interact with windows */
	void on_connect_dialog_hide ();
	void on_connecting_window_hide();
	void on_connection_failure_dialog_response(int response_id);

public:
	static Glib::RefPtr<ClientApplication> create ();

	/* I.e. being called by windows (but maybe not only) */
	void connect (std::string host);
	void failed_to_connect (Glib::ustring error);
	void connected (Glib::RefPtr<Gio::SocketConnection> conn);
};

#endif /* __CLIENT_APPLICATION_H */
