#include "BuildClusterWindow.h"
#include "BuildClusterProxy.h"
#include "ClientApplication.h"
#include "Message.h"
#include <cstdio>

using namespace std;

BuildNodeOverview::BuildNodeOverview(string identity)
	:
		identity(identity),
		m_bMain(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
		m_lIdentity(identity),
		m_lStatus("<initializing>", Gtk::Align::ALIGN_START),
		m_btStart("start"),
		m_btAbort("abort"),
		m_btReset("reset")
{
	set_border_width(5);
	m_ledConnected.set_red(1);

	m_bMain.set_border_width(5);

	/* Layout */
	m_bMain.pack_start(m_ledConnected, false, false, 0);
	m_bMain.pack_start(m_lIdentity, false, false, 0);
	m_bMain.pack_start(m_ledStatus, false, false, 0);
	m_bMain.pack_start(m_lStatus, true, true, 0);
	m_bMain.pack_end(m_btReset, false, false, 0);
	m_bMain.pack_end(m_btAbort, false, false, 0);
	m_bMain.pack_end(m_btStart, false, false, 0);

	add(m_bMain);

	show_all();
}

ClusterOverview::ClusterOverview(BuildClusterWindow *bcwin) :
	Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	bcwin(bcwin),
	build_cluster_proxy(bcwin->build_cluster_proxy),
	m_bNodes(Gtk::Orientation::ORIENTATION_VERTICAL, 0)
{
	set_border_width(10);

	/* UI components */
	m_sw.set_policy(Gtk::POLICY_AUTOMATIC, Gtk::POLICY_ALWAYS);
	m_sw.add(m_bNodes);
	pack_start(m_sw, true, true, 0);

	/* Subscribe to parts of the build cluster (proxy) */
	build_cluster_proxy.subscribe_to_build_node_list(
			BuildClusterProxy::BuildNodeListSubscriber(
				&ClusterOverview::_on_node_list_changed,
				this));
}

void ClusterOverview::on_node_list_changed()
{
	auto ns = build_cluster_proxy.list_build_nodes();

	/* Anything new? */
	for (auto n : ns)
	{
		if (nodes.find(n) == nodes.end())
			add_node(n);
	}
}

void ClusterOverview::_on_node_list_changed(void *pThis)
{
	((ClusterOverview*)pThis)->on_node_list_changed();
}

/**
 * A node with that identity MUST NOT be in the list already. */
void ClusterOverview::add_node(string identity)
{
	BuildNodeOverview n(identity);
	m_bNodes.pack_start(n, false, false, 0);
	n.show();
	nodes.insert({identity, move(n)});
}



BuildClusterWindow::BuildClusterWindow(ClientApplication *c) :
	Gtk::Window(),
	m_client_application(c),
	build_cluster_proxy(c->build_cluster_proxy),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	m_lInfo("The TSClient LEGACY Build System."),
	m_cluster_overview(this)
{
	set_title ("The TSClient LEGACY Build System - Build cluster");
	set_border_width(10);

	/* UI components */
	m_nbMain.append_page(m_cluster_overview, "Cluster overview");

	m_bMain_vbox.pack_start(m_lInfo, false, false, 0);
	m_bMain_vbox.pack_start(m_nbMain, true, true, 0);
	add(m_bMain_vbox);
	m_bMain_vbox.show_all();
}

BuildClusterWindow::~BuildClusterWindow()
{
}
