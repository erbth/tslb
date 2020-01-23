#ifndef __BUILD_CLUSTER_WINDOW_H
#define __BUILD_CLUSTER_WINDOW_H

#include <gtkmm.h>

/* Prototypes */
class ClientApplication;
class stream;
class BuildClusterWindow;

class ClusterOverview : public Gtk::Box
{
private:
	BuildClusterWindow *bcwin;

	/* UI components */

public:
	ClusterOverview(BuildClusterWindow *bcwin);
};

class BuildClusterWindow : public Gtk::Window
{
private:
	ClientApplication *m_client_application;

	/* UI components */
	Gtk::Box m_bMain_vbox;
	Gtk::Label m_lInfo;
	Gtk::Notebook m_nbMain;

	ClusterOverview m_cluster_overview;

public:
	BuildClusterWindow(ClientApplication *c);
	virtual ~BuildClusterWindow() override;
};

#endif
