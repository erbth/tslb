#ifndef __CONNECT_DIALOG_H
#define __CONNECT_DIALOG_H

#include <gtkmm.h>

class ConnectDialog : public Gtk::Window
{
protected:
	Gtk::Label m_lDescription;
	Gtk::Label m_leProxy;
	Gtk::Entry m_eProxy;
	Gtk::Button m_btConnect, m_btAbort;

	Gtk::Box m_bMain_vbox;
	Gtk::ButtonBox m_bBt_box;

public:
	ConnectDialog ();
};

#endif
