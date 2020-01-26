#include "BuildClusterWindow.h"
#include "BuildClusterProxy.h"
#include "ClientApplication.h"
#include "Message.h"
#include <cstdio>
#include <new>

using namespace std;

NodeStartBuildDialog::NodeStartBuildDialog(shared_ptr<BuildNodeProxy::BuildNodeProxy> node)
    :
        node(node)
{
    set_border_width(10);
	set_type_hint(Gdk::WindowTypeHint::WINDOW_TYPE_HINT_DIALOG);

	m_cbtArch.append("i386");
	m_cbtArch.append("amd64");
	m_cbtArch.set_active(1);

    /* UI components */
    auto main_vbox = Gtk::manage(new Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 10));
    main_vbox->pack_start(*Gtk::manage(new Gtk::Label(
		string("Build a package on build node ") + node->identity + ":")), false, false, 0);

	auto bName = Gtk::manage(new Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 5));
	auto bArch = Gtk::manage(new Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 5));
	auto bVersion = Gtk::manage(new Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 5));

	bName->pack_start(*Gtk::manage(new Gtk::Label("Package name")), false, false, 0);
	bName->pack_start(m_eName, false, false, 0);

	bArch->pack_start(*Gtk::manage(new Gtk::Label("Architecture")), false, false, 0);
	bArch->pack_start(m_cbtArch, false, false, 0);

	bVersion->pack_start(*Gtk::manage(new Gtk::Label("Version number")), false, false, 0);
	bVersion->pack_start(m_eVersion, false, false, 0);

	auto bRow = Gtk::manage(new Gtk::Box(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10));
	bRow->pack_start(*bName, true, true, 0);
	bRow->pack_start(*bArch, false, false, 0);
	bRow->pack_start(*bVersion, false, false, 0);

	main_vbox->pack_start(*bRow);

	auto btBuild = Gtk::manage(new Gtk::Button("Build"));
	auto btAbort = Gtk::manage(new Gtk::Button("Abort"));

	auto btBox = Gtk::manage(new Gtk::ButtonBox(Gtk::Orientation::ORIENTATION_HORIZONTAL));
	btBox->pack_start(*btBuild, false, false, 0);
	btBox->pack_start(*btAbort, false, false, 0);
	main_vbox->pack_end(*btBox, false, false, 0);

	add(*main_vbox);

	/* Signale handlers */
	btBuild->signal_clicked().connect(sigc::mem_fun(
		*this, &NodeStartBuildDialog::on_build_clicked));

	btAbort->signal_clicked().connect(sigc::mem_fun(
		*this, &NodeStartBuildDialog::on_abort_clicked));

	show_all();
}

void NodeStartBuildDialog::on_build_clicked()
{
    node->request_start_build(m_eName.get_text(), m_cbtArch.get_active_text(),
			m_eVersion.get_text());

	hide();
}

void NodeStartBuildDialog::on_abort_clicked()
{
	hide();
}

BuildNodeOverview::BuildNodeOverview(shared_ptr<BuildNodeProxy::BuildNodeProxy> node)
	:
		node(node),
		m_bMain(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
		m_lIdentity(node->identity),
		m_lStatus("<initializing>", Gtk::Align::ALIGN_START),
		m_btBuild("build"),
		m_btAbort("abort"),
		m_btReset("reset"),
		m_btMaintenance("maintenance")
{
	set_border_width(5);
	m_ledConnected.set_red(1);

	m_bMain.set_border_width(5);

	/* Layout */
	m_bMain.pack_start(m_ledConnected, false, false, 0);
	m_bMain.pack_start(m_lIdentity, false, false, 0);
	m_bMain.pack_start(m_ledStatus, false, false, 0);
	m_bMain.pack_start(m_lStatus, true, true, 0);
	m_bMain.pack_end(m_btMaintenance, false, false, 0);
	m_bMain.pack_end(m_btReset, false, false, 0);
	m_bMain.pack_end(m_btAbort, false, false, 0);
	m_bMain.pack_end(m_btBuild, false, false, 0);

	add(m_bMain);

	show_all();

    /* Connect signal handlers */
    m_btBuild.signal_clicked().connect(sigc::mem_fun(
        *this, &BuildNodeOverview::on_build_clicked));

    m_btAbort.signal_clicked().connect(sigc::mem_fun(
        *this, &BuildNodeOverview::on_abort_clicked));

    m_btReset.signal_clicked().connect(sigc::mem_fun(
        *this, &BuildNodeOverview::on_reset_clicked));

	m_btMaintenance.signal_clicked().connect(sigc::mem_fun(
		*this, &BuildNodeOverview::on_maintenance_clicked));

	/* Subscribe to the build node (proxy). */
	node->subscribe_to_state(BuildNodeProxy::StateSubscriber(
				&BuildNodeOverview::_on_node_responding_changed,
				&BuildNodeOverview::_on_node_state_changed,
				&BuildNodeOverview::_on_node_error_received,
				this));

	/* Finally update the display to match the node's current state. */
	update_display();
}

BuildNodeOverview::~BuildNodeOverview()
{
	/* Unsubscribe from the build node. The guard is necessary as the objects
     * might have been moved. */
    if (node)
        node->unsubscribe_from_state(this);
}

void BuildNodeOverview::on_build_clicked()
{
	node_start_build_dialog = make_unique<NodeStartBuildDialog>(node);
	node_start_build_dialog->show();
	node_start_build_dialog->signal_hide().connect([this](){node_start_build_dialog = nullptr;});
}

void BuildNodeOverview::on_abort_clicked()
{
	node->request_abort_build();
}

void BuildNodeOverview::on_reset_clicked()
{
	node->request_reset();
}

void BuildNodeOverview::on_maintenance_clicked()
{
	if (node->get_state() == BuildNodeProxy::State::STATE_MAINTENANCE)
		node->request_disable_maintenance();
	else
		node->request_enable_maintenance();
}


/* Subscribing to the build node (proxy) */
void BuildNodeOverview::on_node_responding_changed(bool responding)
{
	if (responding)
	{
		m_ledConnected.set_red(0);
		m_ledConnected.set_green(1);
	}
	else
	{
		m_ledConnected.set_green(0);
		m_ledConnected.set_red(1);
	}
}

void BuildNodeOverview::on_node_state_changed(enum BuildNodeProxy::State state)
{
	switch (state)
	{
		case BuildNodeProxy::State::STATE_IDLE:
			m_lStatus.set_text("idle");
			m_ledStatus.set_red(0);
			m_ledStatus.set_blue(0);
			m_ledStatus.set_green(1);
			break;

		case BuildNodeProxy::State::STATE_BUILDING:
			m_lStatus.set_text("building package `" + node->get_pkg_name() +
					"' version " + node->get_pkg_version() +
					" @" + node->get_pkg_arch());

			m_ledStatus.set_red(1);
			m_ledStatus.set_blue(0);
			m_ledStatus.set_green(.5);
			break;

		case BuildNodeProxy::State::STATE_FINISHED:
			m_lStatus.set_text("finished package `" + node->get_pkg_name() +
					"' version " + node->get_pkg_version() +
					" @" + node->get_pkg_arch());

			m_ledStatus.set_red(1);
			m_ledStatus.set_blue(0);
			m_ledStatus.set_green(1);
			break;

		case BuildNodeProxy::State::STATE_FAILED:
			m_lStatus.set_text("failed to build `" + node->get_pkg_name() +
					"':" + node->get_pkg_version() +
					"@" + node->get_pkg_arch() +
					": " + node->get_fail_reason());

			m_ledStatus.set_red(1);
			m_ledStatus.set_blue(0);
			m_ledStatus.set_green(0);
			break;

		case BuildNodeProxy::State::STATE_MAINTENANCE:
			m_lStatus.set_text("maintenance mode");
			m_ledStatus.set_red(0);
			m_ledStatus.set_blue(1);
			m_ledStatus.set_green(0);
			break;

		case BuildNodeProxy::State::STATE_UNKNOWN:
			m_lStatus.set_text("<unknown>");
			m_ledStatus.set_red(0);
			m_ledStatus.set_blue(0);
			m_ledStatus.set_green(0);
			break;

		default:
			m_lStatus.set_text("<invalid>");
			m_ledStatus.set_red(0);
			m_ledStatus.set_blue(0);
			m_ledStatus.set_green(0);
			break;
	};
}

void BuildNodeOverview::on_node_error_received(string err)
{
	Gtk::MessageDialog d(
			string("Error message from build node ") + node->identity + ": " +
			err,
			false,
			Gtk::MESSAGE_ERROR);

	d.run();
}

void BuildNodeOverview::_on_node_responding_changed(void *pThis, bool responding)
{
    ((BuildNodeOverview*)pThis)->on_node_responding_changed(responding);
}

void BuildNodeOverview::_on_node_state_changed(void *pThis, enum BuildNodeProxy::State state)
{
    ((BuildNodeOverview*)pThis)->on_node_state_changed(state);
}

void BuildNodeOverview::_on_node_error_received(void *pThis, string err)
{
	((BuildNodeOverview*)pThis)->on_node_error_received(err);
}


void BuildNodeOverview::update_display()
{
	/* Manually trigger what would otherwise be triggered by information
	 * delivered from the build node proxy */
	on_node_responding_changed(node->is_responding());
	on_node_state_changed(node->get_state());
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

ClusterOverview::~ClusterOverview()
{
	/* Unsubscribe from the build cluster (proxy) */
	build_cluster_proxy.unsubscribe_from_build_node_list(this);
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
	auto _node = build_cluster_proxy.get_build_node(identity);
	if (_node)
	{
		auto node = make_unique<BuildNodeOverview>(_node);
		m_bNodes.pack_start(*node, false, false, 0);
		node->show();
        nodes.insert({identity, move(node)});
	}
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
