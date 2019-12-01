#include <gtkmm.h>
#include "ClientApplication.h"

using namespace std;

int main (int argc, char** argv)
{
	auto app = ClientApplication::create();
	app->run ();
}
