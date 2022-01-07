"""
Copyright 2022 epiccakeking

This file is part of rpm-ostree-gui.

rpm-ostree-gui is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

rpm-ostree-gui is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with rpm-ostree-gui. If not, see <https://www.gnu.org/licenses/>. 
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib
import json
import subprocess
import threading
import Levenshtein
from pkg_resources import resource_string
import glob
try:
    import hawkey
except:
    hawkey=None

if hawkey:
    sack=hawkey.Sack()
    sack.load_system_repo()

def search(query):
    if not hawkey:
        return []
    return [x.name for x in hawkey.Query(sack).filter(name__glob=f'*{glob.escape(query)}*')]

def templated(c):
    return Gtk.Template(string=resource_string(__name__, c.__gtype_name__+'.ui'))(c)

def spinthread(f):
    def wrapper(self, *args, **kwargs):
        def thread_runner():
            self.thread_lock.acquire()
            self.spinner.start()
            f(self, *args, **kwargs)
            self.spinner.stop()
            self.thread_lock.release()
        threading.Thread(target=thread_runner).start()
    return wrapper

@templated
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__='MainWindow'
    add_menu=Gtk.Template.Child('add_menu')
    package_install_input = Gtk.Template.Child('package_install_input')
    spinner=Gtk.Template.Child('spinner')
    package_list=Gtk.Template.Child('package_list')
    def __init__(self, app):
        super().__init__(application=app)
        self.thread_lock=threading.Lock()
        # Uninstall action
        uninstall_action=Gio.SimpleAction.new('uninstall_selected', None)
        uninstall_action.connect("activate", self.uninstall_selected)
        app.add_action(uninstall_action)
        # Update action
        update_action=Gio.SimpleAction.new('update', None)
        update_action.connect("activate", self.update)
        app.add_action(update_action)
        # Apply live action
        apply_live_action=Gio.SimpleAction.new('apply_live', None)
        apply_live_action.connect("activate", self.apply_live)
        app.add_action(apply_live_action)
        # About action
        about_action=Gio.SimpleAction.new('about', None)
        about_action.connect("activate", lambda *_: AboutPopup(self))
        app.add_action(about_action)
        # Search action
        if hawkey:
            search_action=Gio.SimpleAction.new('search', None)
            search_action.connect("activate", lambda *_: SearchWindow(self))
            app.add_action(search_action)

        self.package_install_input.connect('activate', self.on_install_input)
        self.present()
        self.load()

    @spinthread
    def load(self):
        data=json.loads(subprocess.run(('rpm-ostree', 'status', '--json'), stdout=subprocess.PIPE).stdout)
        self.package_list.set_child(PackageList(sorted(data['deployments'][0]['packages'])))

    @spinthread
    def on_install_input(self, _e):
        self.add_menu.popdown()
        package_name=self.package_install_input.get_buffer().get_text()
        print(package_name)
        proc=subprocess.run(('rpm-ostree', 'install', package_name), stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            GLib.idle_add(self.popup_info, proc.stderr)
        self.load()

    @spinthread
    def uninstall_selected(self, _w, _e):
        selected_packages=[item.name_label.get_label() for item in self.package_list.get_child().get_child().get_selected_rows()]
        if not selected_packages:
            return
        selected_packages.sort()
        proc=subprocess.run(['rpm-ostree', 'uninstall'] + selected_packages, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            GLib.idle_add(self.popup_info, proc.stderr)
        self.load()

    @spinthread
    def update(self, _w, _e):
        proc=subprocess.run(('rpm-ostree', 'upgrade'), stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            GLib.idle_add(self.popup_info, proc.stderr)
        self.load()

    @spinthread
    def apply_live(self, _w, _e):
        proc=subprocess.run(('pkexec', 'rpm-ostree', 'ex', 'apply-live'), stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            GLib.idle_add(self.popup_info, proc.stderr)
        self.load()

    def popup_info(self, msg):
        PopupMessage(self, msg)
        return False


class PopupMessage(Gtk.Dialog):
    def __init__(self, parent, text):
        super().__init__()
        self.set_modal(True)
        self.set_transient_for(parent)
        label=Gtk.Label(label=text)
        self.set_child(label)
        self.present()

class AboutPopup(Gtk.AboutDialog):
    def __init__(self, parent):
        super().__init__(
            authors=(
                'epiccakeking',
            ),
            copyright='Copyright 2022 epiccakeking',
            license_type='GTK_LICENSE_GPL_3_0',
            program_name='RPM OSTree GUI',
        )
        self.set_modal(True)
        self.set_transient_for(parent)
        self.present()


@templated
class SearchWindow(Gtk.Dialog):
    __gtype_name__ = 'SearchWindow'
    search_entry = Gtk.Template.Child('search_entry')
    package_list = Gtk.Template.Child('package_list')
    def __init__(self, parent):
        super().__init__()
        self.set_modal(True)
        self.set_transient_for(parent)
        self.present()
        self.search_entry.connect('activate', self.query)

    def query(self, _e):
        q=self.search_entry.get_buffer().get_text()
        results=search(q)
        results.sort(key=lambda s:Levenshtein.distance(q,s))
        self.package_list.set_child(PackageList(results))


class PackageList(Gtk.ListBox):
    __gtype_name__ = 'PackageList'
    def __init__(self, data):
        super().__init__(
            selection_mode=3,
        )
        for i in data:
            self.append(PackageListItem(i))

@templated
class PackageListItem(Gtk.ListBoxRow):
    __gtype_name__='PackageListItem'
    name_label=Gtk.Template.Child('name_label')
    def __init__(self, name):
        super().__init__()
        self.name_label.set_label(name)
    

# Create a new application
app = Gtk.Application(application_id='io.github.epiccakeking.RpmOstreeGui')
app.connect('activate', MainWindow)

# Run the application
app.run(None)

