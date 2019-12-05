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
	Gtk::Box m_bBuild_master;
	Gtk::Label m_lBuild_master_description;

public:
	ClusterOverview(BuildClusterWindow *bcwin);

	void update_build_master();
};

class BuildClusterWindow : public Gtk::Window
{
private:
	ClientApplication *m_client_application;
	Glib::RefPtr<Gio::SocketConnection> conn;

	char read_buffer[10000];
	std::shared_ptr<stream> input_stream;

	Glib::RefPtr<Gio::Cancellable> async_read_cancellable;
	void async_read_ready(Glib::RefPtr<Gio::AsyncResult> async_result);

	void parse_message(stream msg);
	void parse_build_master_update(stream msg);

public:
	/* The build master */
	bool have_build_master;
	std::string build_master_id;
	uint32_t build_master_yamb_addr;
	bool build_master_seems_dead;

private:
	/* UI components */
	Gtk::Box m_bMain_vbox;
	Gtk::Label m_lInfo;
	Gtk::Notebook m_nbMain;

	ClusterOverview m_cluster_overview;

public:
	BuildClusterWindow(ClientApplication *c);
	virtual ~BuildClusterWindow() override;

	void set_connection(Glib::RefPtr<Gio::SocketConnection> conn);

	/* Actions */
	void request_build_master();

private:
	/* Logics functions */
	void on_build_master_changed();
};

#endif
