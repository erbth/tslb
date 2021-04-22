#include "ClientApplication.h"
#include "ConnectingWindow.h"
#include "BuildClusterWindow.h"
#include <iostream>

using namespace std;

ClientApplication::ClientApplication (const string& yamb_addr)
	: Gtk::Application (), yamb_hub_addr(yamb_addr)
{
	Glib::set_application_name ("TSClient LEGACY Build System Client");
}

Glib::RefPtr<ClientApplication> ClientApplication::create (const string& yamb_addr)
{
	return Glib::RefPtr<ClientApplication> (new ClientApplication(yamb_addr));
}

BuildClusterProxy::BuildClusterProxy &ClientApplication::get_build_cluster_proxy()
{
	return build_cluster_proxy;
}

void ClientApplication::on_activate ()
{
	connecting_window = make_shared<ConnectingWindow> (this);
	connecting_window->signal_hide().connect(
			sigc::mem_fun(*this, &ClientApplication::on_connecting_window_hide));

	add_window (*connecting_window);
	connecting_window->show();

	connecting_window->connect();
}

/* Functions that interact with windows */
void ClientApplication::on_connecting_window_hide()
{
	connecting_window = nullptr;
}

void ClientApplication::failed_to_connect(Glib::ustring error)
{
	connection_failure_dialog = make_shared<Gtk::MessageDialog>(
			"Failed to connect to the yamb hub.",
			false,
			Gtk::MessageType::MESSAGE_ERROR,
			Gtk::ButtonsType::BUTTONS_OK);

	connection_failure_dialog->set_secondary_text(error);
	connection_failure_dialog->signal_response().connect(sigc::mem_fun(*this,
				&ClientApplication::on_connection_failure_dialog_response));

	add_window(*connection_failure_dialog);
	connection_failure_dialog->show();
}

void ClientApplication::connected()
{
	build_cluster_window = make_shared<BuildClusterWindow>(this);
	add_window (*build_cluster_window);
	build_cluster_window->show();
}

void ClientApplication::on_connection_failure_dialog_response(int response_id)
{
	if (connection_failure_dialog)
		connection_failure_dialog->hide();
}


string ClientApplication::get_yamb_hub_addr() const
{
	return yamb_hub_addr;
}
