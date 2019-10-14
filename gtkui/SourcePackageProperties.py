import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from SourcePackage import SourcePackage, SourcePackageVersion
from Architecture import architectures

class SourcePackageProperties(Gtk.Window):
    def __init__(self, name, architecture):
        super().__init__(title="TSClient LEGACY Build System: Source package `%s@%s'" % (name, architectures[architecture]))

        self.sp = SourcePackage(name, architecture, write_intent=True)

        # Grid layout
        self.grid = Gtk.Grid()
        self.add(self.grid)

        # Heading
        self.grid.attach(
                Gtk.Label(label="Edit source package `%s@%s'." % (name, architectures[architecture]), hexpand=True),
                0, 0, 1, 1)

        # Main space
        self.grid.attach(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True), 0, 1, 1, 1)

        # Footer with buttons
        self.footer_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)

        self.bt_ok = Gtk.Button(label="OK")
        self.bt_abort = Gtk.Button(label="Abort")

        self.footer_hbox.pack_start(self.bt_ok, False, False, 5)
        self.footer_hbox.pack_end(self.bt_abort, False, False, 5)

        self.grid.attach(self.footer_hbox, 0, 2, 1, 1)

        # Signals
        self.bt_ok.connect("clicked", lambda bt, s: s.destroy(), self)
        self.bt_abort.connect("clicked", lambda bt, s: s.destroy(), self)

        # Show all widgets
        self.show_all()


class SourcePackageVersionProperties(Gtk.Window):
    def __init__(self, name, architecture, version_number):
        super().__init__(title="TSClient LEGACY Build System: Source package version `%s@%s:%s'" % (name, architectures[architecture], version_number))

        self.sp = SourcePackage(name, architecture, write_intent=True)
        self.spv = self.sp.get_version(version_number)

        # Grid layout
        self.grid = Gtk.Grid(row_spacing=5)
        self.add(self.grid)

        # Heading
        self.grid.attach(
                Gtk.Label(label="Edit source package version `%s@%s:%s'." % (name, architectures[architecture], version_number), hexpand=True),
                0, 0, 1, 1)

        # Main space
        # KV-Attributes
        self.kv_list_store = Gtk.ListStore(str, str)

        for k in self.spv.list_attributes():
            v = self.spv.get_attribute(k)

            i = self.kv_list_store.append()
            self.kv_list_store.set(i, 0, k, 1, str(v))

        ck = Gtk.TreeViewColumn(title="Attribute", cell_renderer=Gtk.CellRendererText(), text=0)
        cv = Gtk.TreeViewColumn(title="Value", cell_renderer=Gtk.CellRendererText(), text=1)
        cv.set_expand(True)

        self.kv_view = Gtk.TreeView(model=self.kv_list_store)
        self.kv_view.append_column(ck)
        self.kv_view.append_column(cv)

        self.kv_list_selection = self.kv_view.get_selection()
        self.kv_list_selection.set_mode(Gtk.SelectionMode.SINGLE)

        frame = Gtk.Frame(label="KV-Attributes")
        frame.add(self.kv_view)
        self.grid.attach(frame, 0, 1, 1, 1)

        # Footer with buttons
        self.footer_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)

        self.bt_ok = Gtk.Button(label="OK")
        self.bt_abort = Gtk.Button(label="Abort")

        self.footer_hbox.pack_start(self.bt_ok, False, False, 5)
        self.footer_hbox.pack_end(self.bt_abort, False, False, 5)

        self.grid.attach(self.footer_hbox, 0, 2, 1, 1)

        # Signals
        self.bt_ok.connect("clicked", lambda bt, s: s.destroy(), self)
        self.bt_abort.connect("clicked", lambda bt, s: s.destroy(), self)

        # Show all widgets
        self.show_all()
