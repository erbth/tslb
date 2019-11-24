#include <gtkmm.h>
#include "ConnectDialog.h"

int main (int argc, char** argv)
{
	auto app = Gtk::Application::create (argc, argv, "tslb.tslb_client");

	/* Show a connect dialog, which in turn will control the rest of the
	 * application. */
	ConnectDialog dialog;
	app->run (dialog);
}
