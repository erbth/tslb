#include "BuildClusterWindow.h"
#include "ClientApplication.h"
#include "Message.h"
#include <cstdio>

using namespace std;

ClusterOverview::ClusterOverview(BuildClusterWindow *bcwin) :
	Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	bcwin(bcwin)
{
	set_border_width(10);

	/* UI components */
}



BuildClusterWindow::BuildClusterWindow(ClientApplication *c) :
	Gtk::Window(),
	m_client_application(c),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	m_lInfo("The TSClient LEGACY Build System."),
	m_cluster_overview(this)
{
	set_title ("The TSClient LEGACY Build System - Build cluster");
	set_border_width(10);

	/* UI components */
	m_nbMain.append_page(m_cluster_overview, "Overview");

	m_bMain_vbox.pack_start(m_lInfo, false, false, 0);
	m_bMain_vbox.pack_start(m_nbMain, true, true, 0);
	add(m_bMain_vbox);
	m_bMain_vbox.show_all();
}

BuildClusterWindow::~BuildClusterWindow()
{
}
