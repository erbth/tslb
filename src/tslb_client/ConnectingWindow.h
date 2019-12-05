#ifndef __CONNECTING_WINDOW_H
#define __CONNECTING_WINDOW_H

#include <gtkmm.h>

/* Prototypes */
class ClientApplication;

class ConnectingWindow : public Gtk::Window
{
protected:
	ClientApplication *m_client_application;

	Gtk::Label m_lInfo;
	Gtk::Button m_btAbort;
	Gtk::Box m_bMain_vbox;
	Gtk::Box m_blInfo;
	Gtk::ButtonBox m_bAbort;

	Glib::RefPtr<Gio::SocketClient> m_socket_client;
	Glib::RefPtr<Gio::Cancellable> m_connect_cancellable;

	void btAbort_clicked();
	bool on_window_delete(GdkEventAny *any_event);
	bool on_window_key_press(GdkEventKey *event);
	void abort();

	void async_connect_ready (Glib::RefPtr<Gio::AsyncResult> async_result);

public:
	ConnectingWindow (ClientApplication *c, std::string host);
};

#endif
