#ifndef __CLIENT_APPLICATION_H
#define __CLIENT_APPLICATION_H

#include <gtkmm.h>
#include <memory>
#include <string>
#include "BuildClusterProxy.h"

/* Prototypes */
class ConnectDialog;
class ConnectingWindow;
class BuildClusterWindow;

class ClientApplication : public Gtk::Application
{
public:
	/* The build cluster proxy. Member order matters here since the cluster
	 * proxy must be destroyed last. Other objects may hold references to it or
	 * to entities (objects) exposed (owned) by it. */
	BuildClusterProxy::BuildClusterProxy build_cluster_proxy;

private:
	std::string yamb_hub_addr;

	std::shared_ptr<ConnectingWindow> connecting_window;
	std::shared_ptr<Gtk::MessageDialog> connection_failure_dialog;
	std::shared_ptr<BuildClusterWindow> build_cluster_window;

	ClientApplication (const std::string& yamb_addr);

	void on_activate ();

	/* Functions that interact with windows */
	void on_connecting_window_hide();
	void on_connection_failure_dialog_response(int response_id);

public:
	static Glib::RefPtr<ClientApplication> create (const std::string& yamb_addr);

	BuildClusterProxy::BuildClusterProxy &get_build_cluster_proxy();

	/* I.e. being called by windows (but maybe not only) */
	void failed_to_connect (Glib::ustring error);
	void connected ();

	std::string get_yamb_hub_addr() const;
};

#endif /* __CLIENT_APPLICATION_H */
