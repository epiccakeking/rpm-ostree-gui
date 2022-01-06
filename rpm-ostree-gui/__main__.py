"""
Copyright 2022 epiccakeking

This file is part of rpm-ostree-gui.

rpm-ostree-gui is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

rpm-ostree-gui is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with rpm-ostree-gui. If not, see <https://www.gnu.org/licenses/>. 
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio
import json
import subprocess
import threading
from pkg_resources import resource_string

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

        self.package_install_input.connect('activate', self.on_install_input)
        self.present()
        self.load()

    @spinthread
    def load(self):
        data=json.loads(subprocess.run(('rpm-ostree', 'status', '--json'), stdout=subprocess.PIPE).stdout)
        self.set_child(DeploymentInfoPage(data['deployments'][0]))
    @spinthread
    def on_install_input(self, _e):
        self.add_menu.popdown()
        package_name=self.package_install_input.get_buffer().get_text()
        print(package_name)
        proc=subprocess.run(('rpm-ostree', 'install', package_name), stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            PopupMessage(self, proc.stderr)
        self.load()
    @spinthread
    def uninstall_selected(self, _w, _e):
        selected_packages=[item.name_label.get_label() for item in self.get_child().package_list.get_selected_rows()]
        if not selected_packages:
            return
        selected_packages.sort()
        proc=subprocess.run(['rpm-ostree', 'uninstall'] + selected_packages, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            PopupMessage(self, proc.stderr)
        self.load()
    @spinthread
    def update(self, _w, _e):
        proc=subprocess.run(('rpm-ostree', 'upgrade'))
        if proc.returncode != 0:
            PopupMessage(self, proc.stderr)
        self.load()
    @spinthread
    def apply_live(self, _w, _e):
        proc=subprocess.run(('pkexec', 'rpm-ostree', 'ex', 'apply-live'))
        if proc.returncode != 0:
            PopupMessage(self, proc.stderr)
        self.load()
        

class PopupMessage(Gtk.Window):
    def __init__(self, parent, text):
        super().__init__()
        self.set_transient_for(parent)
        label=Gtk.Label(label=text)
        self.set_child(label)
        self.present()
    
@templated
class DeploymentInfoPage(Gtk.ScrolledWindow):
    __gtype_name__='DeploymentInfoPage'
    package_list = Gtk.Template.Child('package_list')
    def __init__(self, data):
        super().__init__()
        for i in sorted(data['packages']):
            self.package_list.append(PackageListItem(i))

@templated
class PackageListItem(Gtk.ListBoxRow):
    __gtype_name__='PackageListItem'
    name_label=Gtk.Template.Child('name_label')
    def __init__(self, name):
        super().__init__()
        self.name_label.set_label(name)
    

# Create a new application
app = Gtk.Application(application_id='io.github.epiccakeking.RpmOstreeCli')
app.connect('activate', MainWindow)

# Run the application
app.run(None)

