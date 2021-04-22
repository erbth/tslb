#include <cstdio>
#include <gtkmm.h>
#include "ClientApplication.h"

using namespace std;

int main (int argc, char** argv)
{
	string yamb_addr = "::1";

	if (argc > 2)
	{
		fprintf(stderr, "Usage: %s [<yamb hub>]\n", argv[0]);
		return 1;
	}
	else if (argc == 2)
	{
		yamb_addr = argv[1];
	}

	auto app = ClientApplication::create(yamb_addr);
	return app->run ();
}
