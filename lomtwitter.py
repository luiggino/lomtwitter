#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from gi.repository import Gtk, Notify, GdkPixbuf, GLib, GObject
from datetime import datetime

import gi
import time
import twitter
import dateutil.parser
import requests
import arrow
import os
import tempfile
import signal
import threading
import gettext

gi.require_version('Gtk', '3.0')

try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
except (ImportError, ValueError):
    AppIndicator3 = None

_ = gettext.gettext

consumer_key = ""
consumer_secret = ""
access_token_key = ""
access_token_secret = ""

UI_INFO = """
<ui>
    <popup name='PopupMenu'>
        <menuitem action='Refresh' />
        <menuitem action='About' />
        <separator />
        <menuitem action='Quit' />
    </popup>
</ui>
"""

def async_call(f):
    def do_call():
        try:
            f()
        except Exception:
            pass

    thread = threading.Thread(target=do_call)
    thread.start()


class app_gui:
    """App gui with notify, statusicon, thread, twitter"""
    def __init__(self):
        '''Initialize controller and start thread'''
        GObject.threads_init()
        self.utc = arrow.utcnow()

        Notify.init("LomTwitter")

        action_group = Gtk.ActionGroup("my_actions")
        self.popup_menu(action_group)

        uimanager = self.create_ui_manager()
        uimanager.insert_action_group(action_group)

        self.menu = uimanager.get_widget("/PopupMenu")

        icon_image = os.getcwd() + "/lomtwitter-status-on.svg"

        if AppIndicator3:
            self.indicator = AppIndicator3.Indicator.new('LomTwitter',
                            icon_image,
                            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        else:
            self.status_icon = Gtk.StatusIcon(icon_image)
            self.status_icon.set_from_icon_name()
            self.status_icon.set_tooltip_text('LomTwitter')
            self.status_icon.set_title("LomTwitter")

        if AppIndicator3:
            self.indicator.set_menu(self.menu)
        else:
            self.status_icon.connect('popup-menu', self.popup_menu_cb)


        self.notification = None

        self.connect_twitter()

        async_call(self.get_homeTimeLine)
        async_call(self.refresh)

    def create_ui_manager(self):
        uimanager = Gtk.UIManager()

        uimanager.add_ui_from_string(UI_INFO)

        return uimanager

    def popup_menu(self, action_group):
        action_menu = Gtk.Action("MenuAction", "Refresh", None, None)
        action_group.add_action(action_menu)

        action_refresh = Gtk.Action("Refresh", None, None, Gtk.STOCK_REFRESH)
        action_refresh.connect('activate', self.refresh_twitter)
        action_group.add_action(action_refresh)

        action_about = Gtk.Action("About", None, None, Gtk.STOCK_ABOUT)
        action_about.connect('activate', self.show_about_dialog)
        action_group.add_action(action_about)

        action_quit = Gtk.Action("Quit", None, None, Gtk.STOCK_QUIT)
        action_quit.connect('activate', self.popup_quit)
        action_group.add_action(action_quit)

    def popup_menu_cb(self, icon, button, time):
        """Callback when the popup menu on the status icon has to open"""
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu,
            self.status_icon, button, time)

    def show_about_dialog(self, widget):
        about_dialog = Gtk.AboutDialog()
        authors = ["Luiggino Obreque Minio <luiggino.om@gmail.com>"]

        about_dialog.set_program_name("LomTwitter")
        about_dialog.set_copyright("Copyright \xc2\xa9 2016 Luiggino Obreque Minio")
        about_dialog.set_authors(authors)
        about_dialog.set_website("http://lobreque.me/LomTwitter")
        about_dialog.set_website_label("Luiggino Websiste")
        about_dialog.set_title("About LomTwitter...")
        about_dialog.set_version("0.1")
        about_dialog.set_license_type(Gtk.License.LGPL_3_0)

        logo_image = os.getcwd() + "/logo.svg"
        logo = GdkPixbuf.Pixbuf.new_from_file(logo_image)
        about_dialog.set_logo(logo)
        about_dialog.set_modal(True)

        about_dialog.set_version('0.1')
        about_dialog.run()
        about_dialog.destroy()

    def refresh_twitter(self, widget):
        async_call(self.get_homeTimeLine)

    def connect_twitter(self):
        self.api = twitter.Api(consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token_key=access_token_key,
                access_token_secret=access_token_secret)

        self.api.VerifyCredentials()

    def update_status_icon(self, status):
        """Update the status icon according to the internally statuses"""

        icon_image = os.getcwd() + "/lomtwitter-status-on.svg"
        if status is False:
            icon_image = os.getcwd() + "/lomtwitter-status-off.svg"

        if AppIndicator3:
            self.indicator.set_icon(icon_image)
        else:
            self.status_icon.set_from_icon_name(icon_image)

    def get_homeTimeLine(self, *_):
        print(self.utc.humanize())

        self.update_status_icon(True)

        try:
            statuses = self.api.GetHomeTimeline()
            for status in statuses:
                self.notify(status)
                time.sleep(4)

            self.update_status_icon(False)
            return True
        except KeyboardInterrupt:
            print('Manual break by user')
            self.quit()

    def notify(self, status):
        past = arrow.get(dateutil.parser.parse(status.created_at))
        local = None
        try:
            local = past.humanize(locale='en_US')
        except UnicodeEncodeError:
            local = ''

        summary = u"{0} @{1} - {2}".format(
            status.user.name,
            status.user.screen_name,
            local
            )

        if self.notification is None:
            self.notification = Notify.Notification.new(
                summary,
                status.text
            )
        else:
            self.notification.update(
                summary,
                status.text
            )

        fd, filename = tempfile.mkstemp()
        response = requests.get(
                status.user.profile_image_url)
        os.write(fd, response.content)
        os.close(fd)

        image = GdkPixbuf.Pixbuf.new_from_file(filename)
        self.notification.set_icon_from_pixbuf(image)
        self.notification.set_image_from_pixbuf(image)

        self.notification.show()

    def refresh(self):
        try:
            filename = ''
            GLib.timeout_add_seconds(60*10, self.get_homeTimeLine, filename)
        except KeyboardInterrupt:
            print('Manual break by user')
            self.quit()

    def popup_quit(self, widget):
        if(self.notification):
            self.notification.close()
        Notify.uninit()
        Gtk.main_quit()

    def quit(self):
        if(self.notification):
            self.notification.close()
        Notify.uninit()
        Gtk.main_quit()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = app_gui()
    Gtk.main()
