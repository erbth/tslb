#include "ClientApplication.h"
#include "ConnectDialog.h"
#include "ConnectingWindow.h"
#include "BuildClusterWindow.h"
#include <iostream>

using namespace std;

ClientApplication::ClientApplication () :
	Gtk::Application ("tslb.tslb_client")
{
	Glib::set_application_name ("TSClient LEGACY Build System Client");
}

Glib::RefPtr<ClientApplication> ClientApplication::create ()
{
	return Glib::RefPtr<ClientApplication> (new ClientApplication());
}

void ClientApplication::on_activate ()
{
	connect_dialog = make_shared<ConnectDialog> (this);
	connect_dialog->signal_hide().connect(
			sigc::mem_fun(*this, &ClientApplication::on_connect_dialog_hide));

	add_window (*connect_dialog);
	connect_dialog->show();
}

/* Functions that interact with windows */
void ClientApplication::on_connect_dialog_hide ()
{
	connect_dialog = nullptr;
}

void ClientApplication::connect (std::string host)
{
	connecting_window = make_shared<ConnectingWindow> (this, host);
	connecting_window->signal_hide().connect(
			sigc::mem_fun(*this, &ClientApplication::on_connecting_window_hide));

	add_window (*connecting_window);
	connecting_window->show();
}

void ClientApplication::on_connecting_window_hide()
{
	connecting_window = nullptr;
}

void ClientApplication::failed_to_connect(Glib::ustring error)
{
	connection_failure_dialog = make_shared<Gtk::MessageDialog>(
			"Failed to connect to Client Proxy.",
			false,
			Gtk::MessageType::MESSAGE_ERROR,
			Gtk::ButtonsType::BUTTONS_OK);

	connection_failure_dialog->set_secondary_text(error);
	connection_failure_dialog->signal_response().connect(sigc::mem_fun(*this,
				&ClientApplication::on_connection_failure_dialog_response));

	add_window(*connection_failure_dialog);
	connection_failure_dialog->show();
}

void ClientApplication::connected(Glib::RefPtr<Gio::SocketConnection> conn)
{
	build_cluster_window = make_shared<BuildClusterWindow>(this);
	build_cluster_window->set_connection(conn);
	add_window (*build_cluster_window);
	build_cluster_window->show();
}

void ClientApplication::on_connection_failure_dialog_response(int response_id)
{
	if (connection_failure_dialog)
		connection_failure_dialog->hide();
}
