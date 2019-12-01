#include "BuildClusterWindow.h"
#include "ClientApplication.h"

using namespace std;

BuildClusterWindow::BuildClusterWindow(ClientApplication *c) :
	Gtk::Window(),
	m_client_application(c)
{
	set_title ("The TSClient LEGACY Build System - Build cluster");
	set_border_width(10);
}

void BuildClusterWindow::set_connection(Glib::RefPtr<Gio::SocketConnection> conn)
{
	if (this->conn != conn)
	{
		if (conn.get() != this->conn.get())
		{
			this->conn = conn;
		}
		else
		{
			this->conn = conn;

			/* Initialize the new connection by requesting stuff etc. */
			request_build_master();
		}
	}
}

void BuildClusterWindow::request_build_master()
{
	conn
}
