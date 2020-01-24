#ifndef __BUILD_CLUSTER_WINDOW_H
#define __BUILD_CLUSTER_WINDOW_H

#include <gtkmm.h>
#include <list>
#include <legacy_widgets_for_gtkmm.h>

/* Prototypes */
class ClientApplication;
class stream;
class BuildClusterWindow;

namespace BuildClusterProxy { class BuildClusterProxy; }

class BuildNodeOverview : public Gtk::Frame
{
private:
	const std::string identity;

	/* UI components */
	Gtk::Box m_bMain;
	Lwg::RGBLed m_ledConnected;
	Gtk::Label m_lIdentity;
	Lwg::RGBLed m_ledStatus;
	Gtk::Label m_lStatus;
	Gtk::Button m_btStart;
	Gtk::Button m_btAbort;
	Gtk::Button m_btReset;

public:
	BuildNodeOverview(std::string identity);
};

class ClusterOverview : public Gtk::Box
{
private:
	BuildClusterWindow *bcwin;

public:
	BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;

private:
	/* UI components */
	Gtk::ScrolledWindow m_sw;
	Gtk::Box m_bNodes;

	std::map<std::string,BuildNodeOverview> nodes;

	/* You subscribe to the build cluster proxy */
	void on_node_list_changed();
	static void _on_node_list_changed(void *pThis);

public:
	ClusterOverview(BuildClusterWindow *bcwin);

	void add_node(std::string identity);
};


class BuildClusterWindow : public Gtk::Window
{
private:
	ClientApplication *m_client_application;

public:
	BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;

private:
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
