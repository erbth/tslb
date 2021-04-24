#include "BuildClusterWindow.h"
#include "BuildClusterProxy.h"
#include "BuildNodeConsoleWindow.h"
#include "ClientApplication.h"
#include "Message.h"
#include <algorithm>
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
		m_btMaintenance("maintenance"),
		m_btConsole("console")
{
	set_border_width(5);
	m_ledConnected.set_red(1);

	m_bMain.set_border_width(5);

	/* Layout */
	m_bMain.pack_start(m_ledConnected, false, false, 0);
	m_bMain.pack_start(m_lIdentity, false, false, 0);
	m_bMain.pack_start(m_ledStatus, false, false, 0);
	m_bMain.pack_start(m_lStatus, true, true, 0);

	m_bMain.pack_end(m_btConsole, false, false, 0);
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

	m_btConsole.signal_clicked().connect(sigc::mem_fun(
		*this, &BuildNodeOverview::on_console_clicked));

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

void BuildNodeOverview::on_console_clicked()
{
	auto cw = make_unique<BuildNodeConsoleWindow>(node);
	cw->show();
	auto ptr = cw.get();

	cw->signal_hide().connect([this, ptr](){
		Glib::signal_idle().connect([this, ptr](){
			auto i = console_windows.begin();

			for (; i != console_windows.end(); i++)
				if (i->get() == ptr)
					break;

			if (i != console_windows.end())
				console_windows.erase(i);

			return false;
			});
		});

	console_windows.push_back(move(cw));
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


string BuildNodeOverview::get_identity() const
{
	return node->identity;
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
        nodes.insert({identity, move(node)});

		/* Move the node to its position, which is determined by the RB-tree
		 * map. */
		int i = 0;

		for (const auto &p : nodes)
		{
			if (p.second->get_identity() == identity)
			{
				m_bNodes.reorder_child(*(p.second), i);
				p.second->show();
				break;
			}

			++i;
		}
	}
}


/*************************** An interface to build masters ********************/
MasterInterface::MasterInterface(BuildClusterWindow *bcwin) :
	Gtk::Box(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	bcwin(bcwin),
	build_cluster_proxy(bcwin->build_cluster_proxy),
	m_bMain(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
	m_bMainState(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
	m_ledError(Lwg::LedColor::LED_COLOR_RED),
	m_lError("Error"),
	m_lButtons("Build:"),
	m_btStart("Start"),
	m_btStop("Stop"),
	m_btRefresh("Refresh"),

	m_bBody(Gtk::ORIENTATION_HORIZONTAL, 0),
	m_bPane1(Gtk::ORIENTATION_VERTICAL, 10),
	m_bPane2(Gtk::ORIENTATION_VERTICAL, 10),
	m_sepBody(Gtk::ORIENTATION_VERTICAL),

	m_bRemaining(Gtk::Orientation::ORIENTATION_VERTICAL, 5),
	m_blRemaining(Gtk::Orientation::ORIENTATION_HORIZONTAL, 0),
	m_lRemaining("Remaining packages to process/build:"),
	m_bRemainingFBSurrounding(Gtk::ORIENTATION_VERTICAL, 0),

	m_bBuildQueue(Gtk::Orientation::ORIENTATION_VERTICAL, 5),
	m_blBuildQueue(Gtk::Orientation::ORIENTATION_HORIZONTAL, 0),
	m_lBuildQueue("The build queue:"),
	m_hbBuildQueueLabels(Gtk::Orientation::ORIENTATION_HORIZONTAL, 5),
	m_lBuildQueueFront("Front"),
	m_bBuildQueueFBSurrounding(Gtk::ORIENTATION_VERTICAL, 0),

	m_bValve(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
	m_b2Valve(Gtk::Orientation::ORIENTATION_HORIZONTAL, 10),
	m_lValve("\"Package valve\""),
	m_btOpen("Open"),
	m_btClose("Close"),

	m_bBuildingSet(Gtk::Orientation::ORIENTATION_VERTICAL, 5),
	m_blBuildingSet(Gtk::Orientation::ORIENTATION_HORIZONTAL, 0),
	m_lBuildingSet("Building set:"),
	m_bBuildingSetFBSurrounding(Gtk::ORIENTATION_VERTICAL, 0),

	m_bIdleNodes(Gtk::Orientation::ORIENTATION_VERTICAL, 5),
	m_bBusyNodes(Gtk::Orientation::ORIENTATION_VERTICAL, 5),
	m_blIdleNodes(Gtk::Orientation::ORIENTATION_HORIZONTAL, 0),
	m_blBusyNodes(Gtk::Orientation::ORIENTATION_HORIZONTAL, 0),
	m_lIdleNodes("Idle build nodes:"),
	m_lBusyNodes("Busy build nodes:"),
	m_bIdleNodesFBSurrounding(Gtk::ORIENTATION_VERTICAL, 0),
	m_bBusyNodesFBSurrounding(Gtk::ORIENTATION_VERTICAL, 0),

	m_bConsole(Gtk::ORIENTATION_VERTICAL, 5),
	m_blConsole(Gtk::ORIENTATION_HORIZONTAL, 0),
	m_lConsole("Console:"),
	m_bConsoleH(Gtk::ORIENTATION_HORIZONTAL, 2)
{
	m_fMain.set_border_width(10);
	m_bMain.set_border_width(10);
	m_bPane1.set_border_width(10);
	m_bPane2.set_border_width(10);

	m_cbIdentity.append("");
	m_cbIdentity.set_active(0);

	m_cbArch.append("i386");
	m_cbArch.append("amd64");

	custom_css_provider = Gtk::CssProvider::create();
	custom_css_provider->load_from_data(
		".fb_surrounding_sw { border: 1px solid black }\n"
		".fb_surrounding_box { background-color: #ddd; }\n"
		".label_chunk_fb { background-color: #ddd }\n"
		".label_queue_fb { background-color: #ddd }");

	/* Setup scrolled windows */
	m_swRemaining.get_style_context()->add_class("fb_surrounding_sw");
	m_swRemaining.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_swBuildQueue.get_style_context()->add_class("fb_surrounding_sw");
	m_swBuildQueue.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_swBuildingSet.get_style_context()->add_class("fb_surrounding_sw");
	m_swBuildingSet.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_swIdleNodes.set_border_width(5);
	m_swIdleNodes.get_style_context()->add_class("fb_surrounding_sw");
	m_swIdleNodes.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_swBusyNodes.set_border_width(5);
	m_swBusyNodes.get_style_context()->add_class("fb_surrounding_sw");
	m_swBusyNodes.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	/* Flow box for the remaining set */
	m_bRemainingFBSurrounding.get_style_context()->add_class("fb_surrounding_box");
	m_bRemainingFBSurrounding.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_fbRemaining.get_style_context()->add_class("label_chunk_fb");
	m_fbRemaining.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_lsRemaining = Gio::ListStore<ListStoreText>::create();
	m_fbRemaining.bind_list_store(
			m_lsRemaining,
			sigc::mem_fun(*this, &MasterInterface::on_create_label_list_store));

	m_fbRemaining.set_selection_mode(Gtk::SELECTION_NONE);
	m_fbRemaining.set_homogeneous(true);
	m_fbRemaining.set_column_spacing(5);
	m_fbRemaining.set_row_spacing(5);

	/* Flow box for the build queue */
	m_bBuildQueueFBSurrounding.get_style_context()->add_class("fb_surrounding_box");
	m_bBuildQueueFBSurrounding.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_fbBuildQueue.get_style_context()->add_class("label_queue_fb");
	m_fbBuildQueue.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_lsBuildQueue = Gio::ListStore<ListStoreText>::create();
	m_fbBuildQueue.bind_list_store(
			m_lsBuildQueue,
			sigc::mem_fun(*this, &MasterInterface::on_create_label_list_store));

	m_fbBuildQueue.set_selection_mode(Gtk::SELECTION_NONE);
	m_fbBuildQueue.set_homogeneous(true);
	m_fbBuildQueue.set_column_spacing(5);
	m_fbBuildQueue.set_row_spacing(5);

	/* Flow box for the building set */
	m_bBuildingSetFBSurrounding.get_style_context()->add_class("fb_surrounding_box");
	m_bBuildingSetFBSurrounding.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_fbBuildingSet.get_style_context()->add_class("label_chunk_fb");
	m_fbBuildingSet.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_lsBuildingSet = Gio::ListStore<ListStoreText>::create();
	m_fbBuildingSet.bind_list_store(
			m_lsBuildingSet,
			sigc::mem_fun(*this, &MasterInterface::on_create_label_list_store));

	m_fbBuildingSet.set_selection_mode(Gtk::SELECTION_NONE);
	m_fbBuildingSet.set_homogeneous(true);
	m_fbBuildingSet.set_column_spacing(5);
	m_fbBuildingSet.set_row_spacing(5);

	/* Two flow boxes for idle- and busy nodes */
	m_bIdleNodesFBSurrounding.get_style_context()->add_class("fb_surrounding_box");
	m_bIdleNodesFBSurrounding.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_fbIdleNodes.get_style_context()->add_class("label_chunk_fb");
	m_fbIdleNodes.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_lsIdleNodes = Gio::ListStore<ListStoreText>::create();
	m_fbIdleNodes.bind_list_store(
			m_lsIdleNodes,
			sigc::mem_fun(*this, &MasterInterface::on_create_label_list_store));

	m_fbIdleNodes.set_selection_mode(Gtk::SELECTION_NONE);
	m_fbIdleNodes.set_homogeneous(true);
	m_fbIdleNodes.set_column_spacing(5);
	m_fbIdleNodes.set_row_spacing(5);

	m_bBusyNodesFBSurrounding.get_style_context()->add_class("fb_surrounding_box");
	m_bBusyNodesFBSurrounding.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_fbBusyNodes.get_style_context()->add_class("label_chunk_fb");
	m_fbBusyNodes.get_style_context()->add_provider(
			custom_css_provider,
			GTK_STYLE_PROVIDER_PRIORITY_USER);

	m_lsBusyNodes = Gio::ListStore<ListStoreText>::create();
	m_fbBusyNodes.bind_list_store(
			m_lsBusyNodes,
			sigc::mem_fun(*this, &MasterInterface::on_create_label_list_store));

	m_fbBusyNodes.set_selection_mode(Gtk::SELECTION_NONE);
	m_fbBusyNodes.set_homogeneous(true);
	m_fbBusyNodes.set_column_spacing(5);
	m_fbBusyNodes.set_row_spacing(5);

	/* Policies for showing adjustment sliders of the scrolled windows */
	m_swRemaining.set_policy(Gtk::PolicyType::POLICY_NEVER, Gtk::PolicyType::POLICY_AUTOMATIC);
	m_swBuildQueue.set_policy(Gtk::PolicyType::POLICY_NEVER, Gtk::PolicyType::POLICY_AUTOMATIC);
	m_swBuildingSet.set_policy(Gtk::PolicyType::POLICY_NEVER, Gtk::PolicyType::POLICY_AUTOMATIC);
	m_swIdleNodes.set_policy(Gtk::PolicyType::POLICY_NEVER, Gtk::PolicyType::POLICY_AUTOMATIC);
	m_swBusyNodes.set_policy(Gtk::PolicyType::POLICY_NEVER, Gtk::PolicyType::POLICY_AUTOMATIC);

	/* Minimum sizes */
	m_swBuildQueue.set_size_request(-1, 60);

	/* A terminal for console streaming */
	m_vteConsole = vte_terminal_new();
	vte_terminal_set_cursor_blink_mode(VTE_TERMINAL(m_vteConsole),
			VTE_CURSOR_BLINK_OFF);

	vte_terminal_set_scrollback_lines(VTE_TERMINAL(m_vteConsole), 100000);
	vte_terminal_set_size(VTE_TERMINAL(m_vteConsole), 80, 25);

	gtk_box_pack_start(GTK_BOX(m_bConsoleH.gobj()), m_vteConsole, true, true, 0);

	m_sConsole = gtk_scrollbar_new(GTK_ORIENTATION_VERTICAL,
			gtk_scrollable_get_vadjustment(GTK_SCROLLABLE(m_vteConsole)));

	gtk_box_pack_start(GTK_BOX(m_bConsoleH.gobj()), m_sConsole, false, false, 0);

	/* UI components */
	m_bMain.pack_start(m_ledConnected, false, false, 0);
	m_bMain.pack_start(m_cbIdentity, false, false, 0);

	m_bMainState.pack_start(m_ledState, false, false, 0);
	m_bMainState.pack_start(m_lState, false, false, 0);
	m_bMainState.pack_start(m_ledError, false, false, 0);
	m_bMainState.pack_start(m_lError, false, false, 0);
	m_bMain.pack_start(m_bMainState, true, false, 0);

	m_bMain.pack_start(m_lButtons, false, false, 0);
	m_bMain.pack_start(m_cbArch, false, false, 0);
	m_bMain.pack_start(m_btStart, false, false, 0);
	m_bMain.pack_start(m_btStop, false, false, 0);
	m_bMain.pack_start(m_btRefresh, false, false, 0);

	m_fMain.add(m_bMain);
	pack_start(m_fMain, false, false, 0);

	m_bRemainingFBSurrounding.pack_start(m_fbRemaining, false, false, 0);
	m_swRemaining.add(m_bRemainingFBSurrounding);
	m_blRemaining.pack_start(m_lRemaining, false, false, 0);
	m_bRemaining.pack_start(m_blRemaining, false, false, 0);
	m_bRemaining.pack_start(m_swRemaining, true, true, 0);
	m_bPane1.pack_start(m_bRemaining, true, true, 0);

	m_bBuildQueueFBSurrounding.pack_start(m_fbBuildQueue, false, false, 0);
	m_swBuildQueue.add(m_bBuildQueueFBSurrounding);
	m_hbBuildQueueLabels.pack_start(m_lBuildQueueFront, false, false, 0);
	m_blBuildQueue.pack_start(m_lBuildQueue, false, false, 0);
	m_bBuildQueue.pack_start(m_blBuildQueue, false, false, 0);
	m_bBuildQueue.pack_start(m_hbBuildQueueLabels, false, false, 0);
	m_bBuildQueue.pack_start(m_swBuildQueue, true, true, 0);
	m_bPane1.pack_start(m_bBuildQueue, false, false, 0);

	m_b2Valve.pack_start(m_lValve, false, false, 0);
	m_b2Valve.pack_start(m_ledValve, false, false, 0);
	m_b2Valve.pack_start(m_btOpen, false, false, 0);
	m_b2Valve.pack_start(m_btClose, false, false, 0);
	m_bValve.pack_start(m_b2Valve, true, false, 0);
	m_bPane1.pack_start(m_bValve, false, false, 0);

	m_bBuildingSetFBSurrounding.pack_start(m_fbBuildingSet, false, false, 0);
	m_swBuildingSet.add(m_bBuildingSetFBSurrounding);
	m_blBuildingSet.pack_start(m_lBuildingSet, false, false, 0);
	m_bBuildingSet.pack_start(m_blBuildingSet, false, false, 0);
	m_bBuildingSet.pack_start(m_swBuildingSet, true, true, 0);
	m_bPane1.pack_start(m_bBuildingSet, true, true, 0);

	m_bIdleNodesFBSurrounding.pack_start(m_fbIdleNodes, false, false, 0);
	m_swIdleNodes.add(m_bIdleNodesFBSurrounding);
	m_blIdleNodes.pack_start(m_lIdleNodes, false, false, 0);
	m_bIdleNodes.pack_start(m_blIdleNodes, false, false, 0);
	m_bIdleNodes.pack_start(m_swIdleNodes, true, true, 0);
	m_pNodes.pack1(m_bIdleNodes, true, false);

	m_bBusyNodesFBSurrounding.pack_start(m_fbBusyNodes, false, false, 0);
	m_swBusyNodes.add(m_bBusyNodesFBSurrounding);
	m_blBusyNodes.pack_start(m_lBusyNodes, false, false, 0);
	m_bBusyNodes.pack_start(m_blBusyNodes, false, false, 0);
	m_bBusyNodes.pack_start(m_swBusyNodes, true, true, 0);
	m_pNodes.pack2(m_bBusyNodes, true, false);

	m_bPane1.pack_start(m_pNodes, true, true, 0);

	m_blConsole.pack_start(m_lConsole, false, false, 0);
	m_bConsole.pack_start(m_blConsole, false, false, 0);
	m_bConsole.pack_start(m_bConsoleH, true, true, 0);
	m_bPane2.pack_start(m_bConsole);

	m_bBody.pack_start(m_bPane1, true, true);
	m_bBody.set_center_widget(m_sepBody);
	m_bBody.pack_end(m_bPane2, true, true);
	pack_start(m_bBody, true, true, 0);

	/* Clear the UI */
	update_clear_fields();

	/* Subscribe to parts of the build cluster (proxy) */
	build_cluster_proxy.subscribe_to_build_master_list(
			BuildClusterProxy::BuildMasterListSubscriber(
				&MasterInterface::_on_master_list_changed,
				this));

	update_master_list();

	/* Connect event handlers for UI elements */
	m_cbIdentity.signal_changed().connect(sigc::mem_fun(
		*this, &MasterInterface::on_identity_changed));

	m_btStart.signal_clicked().connect(sigc::mem_fun(
		*this, &MasterInterface::on_start_clicked));

	m_btStop.signal_clicked().connect(sigc::mem_fun(
		*this, &MasterInterface::on_stop_clicked));

	m_btRefresh.signal_clicked().connect(sigc::mem_fun(
		*this, &MasterInterface::on_refresh_clicked));

	m_btOpen.signal_clicked().connect(sigc::mem_fun(
		*this, &MasterInterface::on_open_clicked));

	m_btClose.signal_clicked().connect(sigc::mem_fun(
		*this, &MasterInterface::on_close_clicked));
}

MasterInterface::~MasterInterface()
{
	build_cluster_proxy.unsubscribe_from_build_master_list(this);

	if (build_master)
	{
		build_master->unsubscribe_from_console(cs);
		build_master->unsubscribe(this);
	}
}


void MasterInterface::on_master_list_changed()
{
	update_master_list();
}

void MasterInterface::_on_master_list_changed(void *pThis)
{
	((MasterInterface*)pThis)->on_master_list_changed();
}

void MasterInterface::_on_master_responding_changed(void *pThis)
{
	((MasterInterface*)pThis)->update_master_responding();
}

void MasterInterface::_on_master_remaining_changed(void *pThis)
{
	((MasterInterface*)pThis)->update_master_remaining();
}

void MasterInterface::_on_master_build_queue_changed(void *pThis)
{
	((MasterInterface*)pThis)->update_master_build_queue();
}

void MasterInterface::_on_master_building_set_changed(void *pThis)
{
	((MasterInterface*)pThis)->update_master_building_set();
}

void MasterInterface::_on_master_nodes_changed(void *pThis)
{
	((MasterInterface*)pThis)->update_master_nodes();
}

void MasterInterface::_on_master_state_changed(void *pThis)
{
	((MasterInterface*)pThis)->update_master_state();
}


void MasterInterface::on_error_received(string error_msg)
{
	Gtk::MessageDialog d(
			"Error message from build master",
			false,
			Gtk::MESSAGE_ERROR);

	d.set_secondary_text("Build master: " + error_msg);

	d.run();
}

void MasterInterface::_on_error_received(void *pThis, string error_msg)
{
	((MasterInterface*)pThis)->on_error_received(error_msg);
}


void MasterInterface::new_console_data(const char* data, size_t size)
{
	vte_terminal_feed(VTE_TERMINAL(m_vteConsole), data, size);
}

void MasterInterface::_new_console_data(void* pThis, const char* data, size_t size)
{
	((MasterInterface*)pThis)->new_console_data(data, size);
}


void MasterInterface::reconnect_console()
{
	vte_terminal_reset(VTE_TERMINAL(m_vteConsole), TRUE, TRUE);
	build_master->console_reconnect();
}


/* Update UI components */
void MasterInterface::update_master_list()
{
	int current = m_cbIdentity.get_active_row_number();
	bool master_changed = false;

	auto build_masters = build_cluster_proxy.list_build_masters();

	/* Add new masters */
	for (auto name : build_masters)
	{
		if (find(cbIdentity_values.begin(), cbIdentity_values.end(), name) == cbIdentity_values.end())
		{
			cbIdentity_values.push_back(name);
			m_cbIdentity.append(name);
		}
	}

	/* Remove masters that disappeared */
	int i = 0;

	for (auto iter = cbIdentity_values.begin(); iter != cbIdentity_values.end(); )
	{
		if (i == 0)
		{
			i++;
			continue;
		}

		if (find(build_masters.begin(), build_masters.end(), *iter) == build_masters.end())
		{
			m_cbIdentity.remove_text(i);
			cbIdentity_values.erase(iter++);

			if (i > 0 && current >= i)
			{
				current--;
				master_changed = true;
			}
		}
		else
		{
			iter++;
			i++;
		}
	}

	if (master_changed)
	{
		m_cbIdentity.set_active(current);
		select_master(m_cbIdentity.get_active_text());
	}
}


/**
 * Updates all fields of the build master view from the proxy if a build master
 * is currently selected. */
void MasterInterface::update_master_all()
{
	update_master_responding();
	update_master_remaining();
	update_master_build_queue();
	update_master_building_set();
	update_master_nodes();
	update_master_state();
}

void MasterInterface::update_master_responding()
{
	if (!build_master)
		return;

	bool responding = build_master->is_responding();
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

void MasterInterface::update_master_remaining()
{
	if (!build_master)
		return;

	const set<pair<string, string>> &remaining = build_master->get_remaining();

	/* Remove excess labels and build a set of contained packages in O(n\log{n})
	 * time. */
	set<pair<string, string>> stored_labels;

	for (unsigned i = 0;;)
	{
		auto item = m_lsRemaining->get_item(i);
		if (!item)
			break;

		auto p = make_pair(item->comp1, item->comp2);

		if (remaining.find(p) == remaining.end())
		{
			m_lsRemaining->remove(i);
		}
		else
		{
			stored_labels.insert(move(p));
			++i;
		}
	}

	/* Add missing labels in O(n\log{n}) time. */
	for (const auto &p : remaining)
	{
		if (stored_labels.find(p) == stored_labels.end())
			m_lsRemaining->append(Glib::RefPtr<ListStoreText>(new ListStoreText(
					p.first + ":" + p.second,
					p.first,
					p.second)));
	}
}

void MasterInterface::update_master_build_queue()
{
	if (!build_master)
		return;

	const vector<pair<string, string>> &build_queue = build_master->get_build_queue();

	unsigned cnt_queue = build_queue.size();
	unsigned cnt_store = m_lsBuildQueue->get_n_items();

	for (unsigned i = 0; i < cnt_queue; i++)
	{
		/* Remove elements from the queue's current position until we reach the
		 * new supposed item. */
		while (i < cnt_store)
		{
			if (*(m_lsBuildQueue->get_item(i).get()) == build_queue[i])
				break;

			m_lsBuildQueue->remove(i);
			cnt_store--;
		}

		/* If the i-th element is not in the store already, insert it. */
		if (i == cnt_store)
		{
			auto &p = build_queue[i];

			m_lsBuildQueue->append(Glib::RefPtr<ListStoreText>(new ListStoreText(
					p.first + ":" + p.second,
					p.first,
					p.second)));

			cnt_store++;
		}
	}

	/* Remove excess elements */
	for (unsigned i = cnt_queue; i < cnt_store; i++)
		m_lsBuildQueue->remove(cnt_queue);
}

void MasterInterface::update_master_building_set()
{
	if (!build_master)
		return;

	const set<pair<string, string>> &building_set = build_master->get_building_set();

	/* Remove excess labels and build a set of contained packages in O(n\log{n})
	 * time. */
	set<pair<string, string>> stored_labels;

	for (unsigned i = 0;;)
	{
		auto item = m_lsBuildingSet->get_item(i);
		if (!item)
			break;

		auto p = make_pair(item->comp1, item->comp2);

		if (building_set.find(p) == building_set.end())
		{
			m_lsBuildingSet->remove(i);
		}
		else
		{
			stored_labels.insert(move(p));
			++i;
		}
	}

	/* Add missing labels in O(n\log{n}) time. */
	for (const auto &p : building_set)
	{
		if (stored_labels.find(p) == stored_labels.end())
			m_lsBuildingSet->append(Glib::RefPtr<ListStoreText>(new ListStoreText(
					p.first + ":" + p.second,
					p.first,
					p.second)));
	}
}

void MasterInterface::update_master_nodes()
{
	if (!build_master)
		return;

	/* Idle nodes */
	const vector<string> &idle_nodes = build_master->get_idle_nodes();

	unsigned cnt_idle = idle_nodes.size();
	unsigned cnt_store = m_lsIdleNodes->get_n_items();

	for (unsigned i = 0; i < cnt_idle; i++)
	{
		/* Compare position by position */
		auto item = m_lsIdleNodes->get_item(i);

		if (item)
		{
			if (*(item.get()) != idle_nodes[i])
			{
				m_lsIdleNodes->remove(i);
				item.reset();
			}
		}
		else
		{
			++cnt_store;
		}

		if (!item)
		{
			m_lsIdleNodes->insert(i, Glib::RefPtr<ListStoreText>(new ListStoreText(
					idle_nodes[i], string(), string())));
		}
	}

	/* Remove excess elements */
	for (unsigned i = cnt_idle; i < cnt_store; i++)
		m_lsIdleNodes->remove(cnt_idle);

	/* Busy nodes */
	const vector<string> &busy_nodes = build_master->get_busy_nodes();

	unsigned cnt_busy = busy_nodes.size();
	cnt_store = m_lsBusyNodes->get_n_items();

	for (unsigned i = 0; i < cnt_busy; i++)
	{
		/* Compare position by position */
		auto item = m_lsBusyNodes->get_item(i);

		if (item)
		{
			if (*(item.get()) != busy_nodes[i])
			{
				m_lsBusyNodes->remove(i);
				item.reset();
			}
		}
		else
		{
			++cnt_store;
		}

		if (!item)
		{
			m_lsBusyNodes->insert(i, Glib::RefPtr<ListStoreText>(new ListStoreText(
					busy_nodes[i], string(), string())));
		}
	}

	/* Remove excess elements */
	for (unsigned i = cnt_busy; i < cnt_store; i++)
		m_lsBusyNodes->remove(cnt_busy);
}

/**
 * Update the build master's state and set controls to sensitive as required. */
void MasterInterface::update_master_state()
{
	if (!build_master)
		return;

	enum BuildMasterProxy::state state = build_master->get_state();
	enum architecture arch = build_master->get_architecture();
	bool error = build_master->get_error();
	bool valve = build_master->get_valve();

	/* Set directly state representing display elements */
	switch (state)
	{
		case BuildMasterProxy::BMP_STATE_OFF:
			m_ledState.set_green(0);
			m_ledState.set_red(1);
			m_lState.set_text("State (off)");
			break;

		case BuildMasterProxy::BMP_STATE_IDLE:
			m_ledState.set_red(0);
			m_ledState.set_green(1);
			m_lState.set_text("State (idle)");
			break;

		case BuildMasterProxy::BMP_STATE_COMPUTING:
			m_ledState.set_red(1);
			m_ledState.set_green(1);
			m_lState.set_text("State (computing)");
			break;

		case BuildMasterProxy::BMP_STATE_BUILDING:
			m_ledState.set_red(1);
			m_ledState.set_green(.5);
			m_lState.set_text("State (building)");
			break;

		default:
			m_ledState.set_red(0);
			m_ledState.set_green(0);
			m_lState.set_text("State (<invalid>)");
			break;
	}

	switch (arch)
	{
		case ARCH_I386:
			m_cbArch.set_active(0);
			break;

		case ARCH_AMD64:
			m_cbArch.set_active(1);
			break;

		default:
			fprintf(stderr, "MasterInterface: Invalid architecture.\n");
			break;
	}

	if (error)
		m_ledError.set_intensity(1);
	else
		m_ledError.set_intensity(0);

	if (state != BuildMasterProxy::BMP_STATE_OFF)
	{
		if (valve)
		{
			m_ledValve.set_red(0);
			m_ledValve.set_green(1);
		}
		else
		{
			m_ledValve.set_green(0);
			m_ledValve.set_red(1);
		}
	}
	else
	{
		m_ledValve.set_green(0);
		m_ledValve.set_red(0);
	}

	/* Adapt control sensitivity as required */
	if (state == BuildMasterProxy::BMP_STATE_OFF)
	{
		m_cbArch.set_sensitive(true);
		m_btStart.set_sensitive(true);
	}
	else
	{
		m_cbArch.set_sensitive(false);
		m_btStart.set_sensitive(false);
	}

	if (state == BuildMasterProxy::BMP_STATE_IDLE ||
			state == BuildMasterProxy::BMP_STATE_COMPUTING)
	{
		m_btStop.set_sensitive(true);
	}
	else
	{
		m_btStop.set_sensitive(false);
	}

	if (state != BuildMasterProxy::BMP_STATE_OFF && !error)
	{
		if (valve)
		{
			m_btOpen.set_sensitive(false);
			m_btClose.set_sensitive(true);
		}
		else
		{
			m_btClose.set_sensitive(false);
			m_btOpen.set_sensitive(true);
		}
	}
	else
	{
		m_btOpen.set_sensitive(false);
		m_btClose.set_sensitive(false);
	}
}


/**
 * Clear all fields of the build master view to revert it to a state in which no
 * build master is selected or no information about a build master is available
 * (including no connection). The identity selector is left unchanged. */
void MasterInterface::update_clear_fields()
{
	m_ledConnected.set_green(0);
	m_ledConnected.set_red(1);

	m_ledState.set_red(0);
	m_ledState.set_green(0);
	m_ledState.set_blue(0);
	m_lState.set_text("State (<unknown>)");

	m_ledError.set_intensity(0);

	m_cbArch.set_active(1);
	m_cbArch.set_sensitive(false);

	m_btStart.set_sensitive(false);
	m_btStop.set_sensitive(false);

	m_lsRemaining->remove_all();
	m_lsBuildQueue->remove_all();

	m_ledValve.set_green(0);
	m_ledValve.set_red(0);
	m_btOpen.set_sensitive(false);
	m_btClose.set_sensitive(false);

	m_lsBuildingSet->remove_all();
	m_lsIdleNodes->remove_all();
	m_lsBusyNodes->remove_all();

	vte_terminal_reset(VTE_TERMINAL(m_vteConsole), TRUE, TRUE);
}


void MasterInterface::select_master(string identity)
{
	auto new_build_master = build_cluster_proxy.get_build_master(identity);

	if (new_build_master == build_master)
		return;

	/* Unsubscribe from old build master */
	if (build_master)
	{
		build_master->unsubscribe_from_console(cs);
		build_master->unsubscribe(this);
		update_clear_fields();
	}

	/* Change currently selected build master */
	build_master = new_build_master;

	/* Subscribe to new build master */
	if (build_master)
	{
		build_master->subscribe(BuildMasterProxy::Subscriber(
				_on_master_responding_changed,
				_on_master_remaining_changed,
				_on_master_build_queue_changed,
				_on_master_building_set_changed,
				_on_master_nodes_changed,
				_on_master_state_changed,
				_on_error_received,
				this));

		/* Subscribe to console output */
		cs = build_master->subscribe_to_console(_new_console_data, this);
	}

	/* Update the user interface */
	if (!build_master)
	{
		m_cbIdentity.set_active(0);
		update_clear_fields();
	}
	else
	{
		update_master_all();
	}
}


/* Event handlers */
void MasterInterface::on_identity_changed()
{
	string new_identity = m_cbIdentity.get_active_text();
	select_master(new_identity);
}

void MasterInterface::on_start_clicked()
{
	if (build_master)
	{
		enum architecture arch;
		auto active = m_cbArch.get_active_row_number();

		switch (active)
		{
			case 0:
				arch = ARCH_I386;
				break;

			case 1:
				arch = ARCH_AMD64;
				break;

			default:
				arch = ARCH_INVALID;
				break;
		}

		build_master->start(arch);
	}
}

void MasterInterface::on_stop_clicked()
{
	if (build_master)
		build_master->stop();
}

void MasterInterface::on_refresh_clicked()
{
	build_cluster_proxy.search_for_build_masters();

	if (build_master)
	{
		build_master->refresh();
		reconnect_console();
	}
}

void MasterInterface::on_open_clicked()
{
	if (build_master)
		build_master->open();
}

void MasterInterface::on_close_clicked()
{
	if (build_master)
		build_master->close();
}


Gtk::Widget* MasterInterface::on_create_label_list_store(
		const Glib::RefPtr<ListStoreText> &item)
{
	auto label = Gtk::make_managed<Gtk::Label>(item->text);
	label->set_selectable();
	return label;
}


/******************************* The main window ******************************/
BuildClusterWindow::BuildClusterWindow(ClientApplication *c) :
	Gtk::Window(),
	m_client_application(c),
	build_cluster_proxy(c->build_cluster_proxy),
	m_bMain_vbox(Gtk::Orientation::ORIENTATION_VERTICAL, 10),
	m_lInfo("The TSClient LEGACY Build System."),
	m_cluster_overview(this),
	m_master_interface(this)
{
	set_title ("The TSClient LEGACY Build System - Build cluster");
	set_border_width(10);

	/* UI components */
	m_nbMain.append_page(m_cluster_overview, "Cluster overview");
	m_nbMain.append_page(m_master_interface, "Build master");

	m_bMain_vbox.pack_start(m_lInfo, false, false, 0);
	m_bMain_vbox.pack_start(m_nbMain, true, true, 0);
	add(m_bMain_vbox);
	m_bMain_vbox.show_all();
}

BuildClusterWindow::~BuildClusterWindow()
{
}
