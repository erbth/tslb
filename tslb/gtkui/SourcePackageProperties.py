import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from tslb.SourcePackage import SourcePackage, SourcePackageVersion
from tslb.Architecture import architectures

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


class SourcePackageVersionAttributes(Gtk.Window):
    def __init__(self, name, architecture, version_number):
        super().__init__(title="TSClient LEGACY Build System: Source package version `%s@%s:%s'" % (name, architectures[architecture], version_number))

        self.sp_name = name
        self.sp_architecture = architecture
        self.sp_version_number = version_number

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

        scrolled_frame = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scrolled_frame.add(frame)
        self.grid.attach(scrolled_frame, 0, 1, 1, 1)

        # Footer with buttons
        self.footer_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)

        self.bt_refresh = Gtk.Button(label="Refresh")
        self.bt_close = Gtk.Button(label="Close")

        self.footer_hbox.pack_start(self.bt_refresh, False, False, 5)
        self.footer_hbox.pack_end(self.bt_close, False, False, 5)

        self.grid.attach(self.footer_hbox, 0, 2, 1, 1)

        # Signals
        self.bt_refresh.connect("clicked", lambda bt, s: s.refresh(), self)
        self.bt_close.connect("clicked", lambda bt, s: s.destroy(), self)

        # Initially load data
        self.refresh()

        # Show all widgets
        self.show_all()

    def refresh(self):
        self.kv_list_store.clear()

        sp = SourcePackage(self.sp_name, self.sp_architecture)
        spv = sp.get_version(self.sp_version_number)

        for k in spv.list_attributes():
            v = spv.get_attribute(k)

            i = self.kv_list_store.append()
            self.kv_list_store.set(i, 0, k, 1, str(v))
