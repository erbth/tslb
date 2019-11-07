import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from SourcePackageProperties import SourcePackageProperties, SourcePackageVersionAttributes
from Constraint import DependencyList

from VersionNumber import VersionNumber
from SourcePackage import SourcePackageList, SourcePackage, SourcePackageVersion
from Architecture import architectures, amd64
from BinaryPackage import BinaryPackage

"""
This is the main window of TSClient LEGACY's buid system's Gtk+ ui.
"""

class MainWindow(object):
    def __init__(self):
        # The window itself
        self.window = Gtk.Window(title="TSClient LEGACY Build System")

        self.main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.window.add(self.main_vbox)

        self.top_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.main_vbox.pack_start(self.top_hbox, False, True, 5)

        self.top_hbox.pack_start(Gtk.Label(label="A Gtk+ 3 gui for the TSClient LEGACY build system."), True, True, 5)

        self.btupdate = Gtk.Button(label="update")
        self.top_hbox.pack_start(self.btupdate, False, False, 5)

        # The notebook
        self.nb_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_vbox.pack_start(self.nb_hbox, True, True, 5)
        self.nb = Gtk.Notebook()
        self.nb_hbox.pack_start(self.nb, True, True, 5)

        # Page 1 for packages
        self.nb_page1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.nb.append_page(self.nb_page1, Gtk.Label(label="Source packages"))

        self.p1hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.nb_page1.pack_start(self.p1hbox, True, True, 5)

        # Side pane to select packages
        # Model: (source package name, version, binary package name, version, display name)
        self.pkg_treestore = Gtk.TreeStore(str, str, str, str, str)
        self.pkg_treeview = Gtk.TreeView.new_with_model(self.pkg_treestore)
        self.pkg_treeview.set_property('hexpand', True)

        cr = Gtk.CellRendererText()
        self.pkg_treeview.append_column(
                Gtk.TreeViewColumn(title="Packages", cell_renderer=cr, text=4))

        self.pkg_treeview_sel = self.pkg_treeview.get_selection()
        self.pkg_treeview_sel.set_mode(Gtk.SelectionMode.SINGLE)

        self.pkg_scrolled_treeview = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.ALWAYS)
        self.pkg_scrolled_treeview.add(self.pkg_treeview)
        self.p1hbox.pack_start(self.pkg_scrolled_treeview, False, True, 5)

        # Package overview
        self.pkg_ovr_frame = Gtk.Frame()
        self.p1hbox.pack_start(self.pkg_ovr_frame, True, True, 5)

        # Page 2 for builds
        self.nb_page2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.nb.append_page(self.nb_page2, Gtk.Label(label="Builds"))

        self.p2hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.nb_page2.pack_start(self.p2hbox, True, True, 5)

        # Page 3 for the build cluster
        self.nb_page3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.nb.append_page(self.nb_page3, Gtk.Label(label="Build cluster"))

        self.p3hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.nb_page3.pack_start(self.p3hbox, True, True, 5)

        # Connect signals
        self.window.connect("delete-event", Gtk.main_quit)
        self.pkg_treeview_sel.connect("changed", self.pkg_treeview_sel_changed)
        self.btupdate.connect("clicked", self.update_data)

        # Show widgets
        self.window.show_all()

        # Source package list
        self.spl = SourcePackageList(amd64)

        # Update data
        self.update_data()

    def update_packages(self):
        self.pkg_treestore.clear()

        tl = self.spl.list_source_packages()
        for pn, a in tl:
            i = self.pkg_treestore.append(None)
            self.pkg_treestore.set(i, 0, pn, 1, "", 2, "", 3, "", 4, pn)

            sp = SourcePackage(pn, a)
            vs = sp.list_version_numbers()
            for vn in vs:
                j = self.pkg_treestore.append(i)
                self.pkg_treestore.set(j, 0, pn, 1, str(vn), 2, "", 3, "", 4, str(vn))

                sv = sp.get_version(vn)
                allbps = sv.list_all_binary_packages()
                for bpn in allbps:
                    k = self.pkg_treestore.append(j)
                    self.pkg_treestore.set(k, 0, pn, 1, str(vn), 2, bpn, 3, "", 4, bpn)

                    bpvs = sv.list_binary_package_version_numbers(bpn)
                    for bpv in bpvs:
                        l = self.pkg_treestore.append(k)
                        self.pkg_treestore.set(l, 0, pn, 1, str(vn), 2, bpn, 3, str(bpv), 4, str(bpv))

    def update_data(self, *args, **kwargs):
        self.update_packages()

    def pkg_treeview_sel_changed(self, selection):
        # Clear package overview
        cs = self.pkg_ovr_frame.get_children()

        for c in cs:
            self.pkg_ovr_frame.remove(c)

        # Populate package overview
        sel = selection.get_selected()
        if sel:
            i = sel[1]

            s, sv, b, bv = self.pkg_treestore.get(i, 0, 1, 2, 3)

            if not sv and not b and not bv:
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                self.pkg_ovr_frame.add(vbox)

                fr_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                vbox.pack_start(fr_hbox, False, True, 5)

                fr_hbox.pack_start(Gtk.Label(label="Source package %s:" % s), True, True, 5)
                bt_edit = Gtk.Button(label="edit")
                fr_hbox.pack_start(bt_edit, False, True, 5)

                bt_edit.connect("clicked", lambda bt, n, a: SourcePackageProperties(n, a), s, amd64)

            elif not b and not bv:
                # Source package version tab
                sp = SourcePackage(s, amd64, write_intent=True)
                spv = sp.get_version(sv)

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                self.pkg_ovr_frame.add(vbox)

                fr_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                vbox.pack_start(fr_hbox, False, True, 5)

                fr_hbox.pack_start(Gtk.Label(label="Source package version `%s:%s'" % (s, sv)), True, True, 5)
                bt_attributes = Gtk.Button(label="Attributes")
                fr_hbox.pack_start(bt_attributes, False, True, 5)

                bt_attributes.connect("clicked", lambda bt, n, a, sv: SourcePackageVersionAttributes(n, a, sv), s, amd64, sv)

                # More tabs inside the tab.
                nb = Gtk.Notebook()
                vbox.pack_start(nb, True, True, 5)

                # Build procedure
                pbuild = Gtk.Grid()
                nb.append_page (pbuild, Gtk.Label(label="Build procedure"))

                # Compiletime dependencies
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                box.pack_start(Gtk.Label(label="Compiletime dependencies"), False, False, 5)

                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                box.pack_start(hbox, True, True, 5)

                liststore = Gtk.ListStore(str, str)

                if not spv.has_attribute('cdeps'):
                    spv.set_attribute('cdeps', DependencyList())

                cdeps = spv.get_attribute('cdeps')
                for dep in sorted(cdeps.get_required()):
                    i = liststore.append()
                    liststore.set(i, 0, dep, 1, cdeps.get_constraint_list(dep))

                c1 = Gtk.TreeViewColumn(title="Source package", cell_renderer=Gtk.CellRendererText(), text=0)
                c1.set_expand(True)
                c2 = Gtk.TreeViewColumn(title="Constraints", cell_renderer=Gtk.CellRendererText(), text=1)

                listview = Gtk.TreeView.new_with_model(liststore)
                listview.append_column(c1)
                listview.append_column(c2)

                hbox.pack_start(listview, True, True, 0)

                btbox = Gtk.ButtonBox(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                hbox.pack_start(btbox, False, True, 0)

                pbuild.attach(box, 0, 0, 1, 1)

            elif not bv:
                # Binary package tab
                self.pkg_ovr_frame.add(Gtk.Label(label="Binary package %s selected." % b))

            else:
                sp = SourcePackage(s, amd64)
                spv = sp.get_version(sv)
                bp = spv.get_binary_package(b, bv)

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                self.pkg_ovr_frame.add(vbox)

                vbox.pack_start(Gtk.Label(label="Binary package `%s' version %s" % (b, bv)), False, True, 5)

                # Files
                files_frame = Gtk.Frame(label="Files")
                vbox.pack_start(files_frame, True, True, 5)

                files_list_store = Gtk.ListStore(str, str)

                for p, sha512 in bp.get_files():
                    i = files_list_store.append()
                    files_list_store.set(i, 0, p, 1, sha512)

                files_list_view = Gtk.TreeView.new_with_model(files_list_store)

                c1 = Gtk.TreeViewColumn(title="Path", cell_renderer=Gtk.CellRendererText(), text=0)
                c1.set_expand(True)
                files_list_view.append_column(c1)

                files_list_view.append_column(Gtk.TreeViewColumn(
                    title="SHA512 sum", cell_renderer=Gtk.CellRendererText(), text=1))

                files_list_view_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                files_frame.add(files_list_view_box)
                files_list_view_sw = Gtk.ScrolledWindow(vscrollbar_policy=Gtk.PolicyType.ALWAYS)
                files_list_view_sw.add(files_list_view)
                files_list_view_box.pack_start(files_list_view_sw, True, True, 5)

            self.pkg_ovr_frame.show_all()
