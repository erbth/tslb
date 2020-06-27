#ifndef __BUILD_CLUSTER_WINDOW_H
#define __BUILD_CLUSTER_WINDOW_H

#include <gtkmm.h>
#include <map>
#include <memory>
#include <list>
#include <legacy_widgets_for_gtkmm.h>
#include "BuildNodeProxy.h"
#include "BuildMasterProxy.h"

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


/*********************** An interface to build masters ************************/
class ListStoreText : public Glib::Object
{
public:
	std::string text;

	/* For simpler comparison */
	std::string comp1;
	std::string comp2;

	ListStoreText(std::string text, std::string comp1, std::string comp2)
		: text(text), comp1(comp1), comp2(comp2)
	{}

	bool operator==(const std::pair<const std::string, const std::string>& p) const
	{
		return p.first == comp1 && p.second == comp2;
	}
};

class MasterInterface : public Gtk::Box
{
private:
	BuildClusterWindow *bcwin;

	BuildClusterProxy::BuildClusterProxy &build_cluster_proxy;
	std::shared_ptr<BuildMasterProxy::BuildMasterProxy> build_master;

private:
	/* UI components */
	Gtk::Frame			m_fMain;
	Gtk::Box			m_bMain;
	Lwg::RGBLed			m_ledConnected;
	Gtk::ComboBoxText	m_cbIdentity;
	Gtk::Box			m_bMainState;
	Lwg::RGBLed			m_ledState;
	Gtk::Label			m_lState;
	Lwg::Led			m_ledError;
	Gtk::Label			m_lError;
	Gtk::Label			m_lButtons;
	Gtk::ComboBoxText	m_cbArch;
	Gtk::Button			m_btStart;
	Gtk::Button			m_btStop;
	Gtk::Button			m_btRefresh;

	Gtk::Box			m_bRemaining;
	Gtk::Box			m_blRemaining;
	Gtk::Label			m_lRemaining;
	Gtk::ScrolledWindow	m_swRemaining;
	Gtk::FlowBox		m_fbRemaining;
	Glib::RefPtr<Gio::ListStore<ListStoreText>> m_lsRemaining;

	Gtk::Box			m_bBuildQueue;
	Gtk::Box			m_blBuildQueue;
	Gtk::Label			m_lBuildQueue;
	Gtk::Box			m_hbBuildQueueLabels;
	Gtk::Label			m_lBuildQueueFront;
	Gtk::ScrolledWindow m_swBuildQueue;
	Gtk::FlowBox		m_fbBuildQueue;
	Glib::RefPtr<Gio::ListStore<ListStoreText>> m_lsBuildQueue;

	Gtk::Box			m_bValve;
	Gtk::Box			m_b2Valve;
	Gtk::Label			m_lValve;
	Lwg::RGBLed			m_ledValve;
	Gtk::Button			m_btOpen;
	Gtk::Button			m_btClose;

	Gtk::Box			m_bBuildingSet;
	Gtk::Box			m_blBuildingSet;
	Gtk::Label			m_lBuildingSet;
	Gtk::ScrolledWindow	m_swBuildingSet;

	Gtk::Paned			m_pNodes;
	Gtk::Box			m_bIdleNodes;
	Gtk::Box			m_bBusyNodes;
	Gtk::Box			m_blIdleNodes;
	Gtk::Box			m_blBusyNodes;
	Gtk::Label			m_lIdleNodes;
	Gtk::Label			m_lBusyNodes;
	Gtk::ScrolledWindow	m_swIdleNodes;
	Gtk::ScrolledWindow	m_swBusyNodes;

	Glib::RefPtr<Gtk::CssProvider> custom_css_provider;

	std::list<std::string> cbIdentity_values;

	/* You subscribe to the build cluster proxy */
	void on_master_list_changed();
	static void _on_master_list_changed(void *pThis);

	/* Subscribing to a build master */
	static void _on_master_responding_changed(void* pThis);
	static void _on_master_remaining_changed(void* pThis);
	static void _on_master_build_queue_changed(void* pThis);
	static void _on_master_building_set_changed(void* pThis);
	static void _on_master_nodes_changed(void* pThis);
	static void _on_master_state_changed(void* pThis);

	void on_error_received(std::string error_msg);
	static void _on_error_received(void* pThis, std::string error_msg);

	/* Update UI components */
	void update_master_list();

	void update_master_all();
	void update_master_responding();
	void update_master_remaining();
	void update_master_build_queue();
	void update_master_state();

	void update_clear_fields();

	/* Respond to user actions */
	void select_master(std::string identity);

	/* Event handlers */
	void on_identity_changed();
	void on_start_clicked();
	void on_stop_clicked();
	void on_refresh_clicked();
	void on_open_clicked();
	void on_close_clicked();

	/* Building labels from ListStoreText items in ListStores */
	Gtk::Widget* on_create_label_list_store(const Glib::RefPtr<ListStoreText> &item);


public:
	MasterInterface(BuildClusterWindow *bcwin);
	~MasterInterface();
};


/******************************* The main window ******************************/
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
	MasterInterface m_master_interface;

public:
	BuildClusterWindow(ClientApplication *c);
	virtual ~BuildClusterWindow() override;
};

#endif
