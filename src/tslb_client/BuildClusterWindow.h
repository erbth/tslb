#ifndef __BUILD_CLUSTER_WINDOW_H
#define __BUILD_CLUSTER_WINDOW_H

#include <gtkmm.h>
#include <map>
#include <memory>
#include <list>
#include <legacy_widgets_for_gtkmm.h>
#include "BuildNodeProxy.h"

/* Prototypes */
class ClientApplication;
class stream;
class BuildClusterWindow;
class BuildNodeConsoleWindow;

namespace BuildClusterProxy { class BuildClusterProxy; }

class NodeStartBuildDialog : public Gtk::Window
{
private:
	std::shared_ptr<BuildNodeProxy::BuildNodeProxy> node;

	/* UI components */
	Gtk::Entry m_eName;
	Gtk::ComboBoxText m_cbtArch;
	Gtk::Entry m_eVersion;

	void on_build_clicked();
	void on_abort_clicked();

public:
	NodeStartBuildDialog(std::shared_ptr<BuildNodeProxy::BuildNodeProxy> node);
};

class BuildNodeOverview : public Gtk::Frame
{
private:
	/* The build node proxy */
	std::shared_ptr<BuildNodeProxy::BuildNodeProxy> node;

	/* UI components */
	Gtk::Box m_bMain;
	Lwg::RGBLed m_ledConnected;
	Gtk::Label m_lIdentity;
	Lwg::RGBLed m_ledStatus;
	Gtk::Label m_lStatus;
	Gtk::Button m_btBuild;
	Gtk::Button m_btAbort;
	Gtk::Button m_btReset;
	Gtk::Button m_btMaintenance;
	Gtk::Button m_btConsole;

	std::unique_ptr<Gtk::Window> node_start_build_dialog;

	std::list<std::unique_ptr<BuildNodeConsoleWindow>> console_windows;

	/* Signal handlers */
	void on_build_clicked();
	void on_abort_clicked();
	void on_reset_clicked();
	void on_maintenance_clicked();
	void on_console_clicked();

	/* You subscribe to the build node. Therefore you need these callbacks. */
	void on_node_responding_changed(bool responding);
	void on_node_state_changed(enum BuildNodeProxy::State state);
	void on_node_error_received(std::string err);

	static void _on_node_responding_changed(void *pThis, bool);
	static void _on_node_state_changed(void *pThis, enum BuildNodeProxy::State);
	static void _on_node_error_received(void *pThis, std::string err);

public:
	BuildNodeOverview(std::shared_ptr<BuildNodeProxy::BuildNodeProxy>);
	BuildNodeOverview(const BuildNodeOverview &o) = delete;
	BuildNodeOverview(BuildNodeOverview &&o) = delete;
	~BuildNodeOverview();

	void update_display();
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

	std::map<std::string,std::unique_ptr<BuildNodeOverview>> nodes;

	/* You subscribe to the build cluster proxy */
	void on_node_list_changed();
	static void _on_node_list_changed(void *pThis);

public:
	ClusterOverview(BuildClusterWindow *bcwin);
	~ClusterOverview();

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
