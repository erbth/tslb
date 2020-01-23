#ifndef __CONNECTING_WINDOW_H
#define __CONNECTING_WINDOW_H

#include <gtkmm.h>

/* Prototypes */
class ClientApplication;
namespace BuildClusterProxy { class BuildClusterProxy; }

class ConnectingWindow : public Gtk::Window
{
protected:
	ClientApplication *m_client_application;
	BuildClusterProxy::BuildClusterProxy &m_build_cluster_proxy;

	Gtk::Label m_lInfo;
	Gtk::Button m_btAbort;
	Gtk::Box m_bMain_vbox;
	Gtk::Box m_blInfo;
	Gtk::ButtonBox m_bAbort;

	void btAbort_clicked();
	bool on_window_delete(GdkEventAny *any_event);
	bool on_window_key_press(GdkEventKey *event);
	void abort();

	/* Get notified when the connection is established */
	void connection_established();
	void connection_failed(std::string error);

	static void _connection_established(void *pThis);
	static void _connection_failed(void *pThis, std::string error);

public:
	ConnectingWindow (ClientApplication *c);
	virtual ~ConnectingWindow();

	void connect();
};

#endif
