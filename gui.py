#
# gui.py - Graphical front end for anaconda
#
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 1999-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import errno
import iutil
import string
import time
import isys
import sys
import parted
import gtk
import gtk.glade
import htmlbuffer
import rpm
import kudzu
import gettext
from language import expandLangs
from splashscreen import splashScreenPop
from flags import flags
from constants import *

from rhpl.log import log
from rhpl.translate import _, N_

rpm.addMacro("_i18ndomains", "redhat-dist")
isys.bind_textdomain_codeset("redhat-dist", "UTF-8")

StayOnScreen = "stayOnScreen"
mainWindow = None

stepToClass = {
    "language" : ("language_gui", "LanguageWindow"),
    "keyboard" : ("keyboard_gui", "KeyboardWindow"),
    "mouse" : ("mouse_gui", "MouseWindow"),
    "welcome" : ("welcome_gui", "WelcomeWindow"),
    "installtype" : ("installpath_gui", "InstallPathWindow"),
    "zfcpconfig" : ("zfcp_gui", "ZFCPWindow"),
    "partitionmethod" : ("partmethod_gui", "PartitionMethodWindow"),
    "partition" : ("partition_gui", "PartitionWindow"),
    "autopartition" : ("partition_gui", "AutoPartitionWindow"),
    "findinstall" : ("examine_gui", "UpgradeExamineWindow"),
    "addswap" : ("upgrade_swap_gui", "UpgradeSwapWindow"),
    "upgrademigratefs" : ("upgrade_migratefs_gui", "UpgradeMigrateFSWindow"),
    "fdisk" : ("fdisk_gui", "FDiskWindow"),
    "bootloader": ("bootloader_main_gui", "MainBootloaderWindow"),
    "bootloaderadvanced": ("bootloader_advanced_gui", "AdvancedBootloaderWindow"),
    "upgbootloader": ("upgrade_bootloader_gui", "UpgradeBootloaderWindow"),
    "network" : ("network_gui", "NetworkWindow"),
    "firewall" : ("firewall_gui", "FirewallWindow"),
    "languagesupport" : ("language_support_gui", "LanguageSupportWindow"),
    "timezone" : ("timezone_gui", "TimezoneWindow"),
    "accounts" : ("account_gui", "AccountWindow"),
    "authentication" : ("auth_gui", "AuthWindow"),
    "desktopchoice": ("desktop_choice_gui", "DesktopChoiceWindow"),
    "package-selection" : ("package_gui", "PackageSelectionWindow"),
    "indivpackage" : ("package_gui", "IndividualPackageSelectionWindow"),
    "dependencies" : ("dependencies_gui", "UnresolvedDependenciesWindow"),
    "videocard" : ("xconfig_gui", "XConfigWindow"),
    "monitor" : ("xconfig_gui", "MonitorWindow"),
    "xcustom" : ("xconfig_gui", "XCustomWindow"),
    "confirminstall" : ("confirm_gui", "InstallConfirmWindow"),
    "confirmupgrade" : ("confirm_gui", "UpgradeConfirmWindow"),
    "finishxconfig" : None,
    "install" : ("progress_gui", "InstallProgressWindow_NEW"),
    "bootdisk" : ("bootdisk_gui", "BootdiskWindow"),
    "complete" : ("congrats_gui", "CongratulationWindow"),
}

if iutil.getArch() == 'sparc':
    stepToClass["bootloader"] = ("silo_gui", "SiloWindow")
elif iutil.getArch() == 's390':
    stepToClass["bootloader"] = ("zipl_gui", "ZiplWindow")

#
# Stuff for screenshots
#
screenshotDir = None
screenshotIndex = 0

def copyScreenshots():
    global screenshotIndex
    global screenshotDir
    
    # see if any screenshots taken
    if screenshotIndex == 0:
	return

    destDir = "/mnt/sysimage/root/anaconda-screenshots"
    if not os.access(destDir, os.R_OK):
	try:
	    os.mkdir(destDir, 0750)
	except:
	    window = MessageWindow("Error Saving Screenshot", 
				   _("An error occurred copying the "
				     "screenshots over."), type="warning")
	    return

    # copy all png's over
    for f in os.listdir(screenshotDir):
	(path, fname) = os.path.split(f)
	(b, ext) = os.path.splitext(f)
	if ext == ".png":
	    iutil.copyFile(screenshotDir + '/' + f,
			   destDir + '/' + fname)

    window = MessageWindow(_("Screenshots Copied"), 
			   _("The screenshots have been saved into the "
			     "directory:\n\n"
			     "\t/root/anaconda-screenshots/\n\n"
			     "You can access these when you reboot and "
			     "login as root."))



def takeScreenShot():
    global screenshotIndex
    global screenshotDir

    if screenshotDir is None:
	screenshotDir = "/tmp/ramfs/anaconda-screenshots"

	if  not os.access(screenshotDir, os.R_OK):
	    try:
		os.mkdir(screenshotDir)
	    except:
		screenshotDir = None
		return

    try:
	screenshot = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, gtk.FALSE, 8,
				    gtk.gdk.screen_width(), gtk.gdk.screen_height())
	screenshot.get_from_drawable(gtk.gdk.get_default_root_window(),
				     gtk.gdk.colormap_get_system(),
				     0, 0, 0, 0,
				     gtk.gdk.screen_width(), gtk.gdk.screen_height())

	if screenshot:
	    while (1):
		sname = "screenshot-%04d.png" % ( screenshotIndex,)
		if not os.access(screenshotDir + '/' + sname, os.R_OK):
		    break

		screenshotIndex = screenshotIndex + 1
		if screenshotIndex > 9999:
		    log("Too many screenshots!")
		    return

	    screenshot.save (screenshotDir + '/' + sname, "png")
	    screenshotIndex = screenshotIndex + 1

	    window = MessageWindow(_("Saving Screenshot"), 
				   _("A screenshot named '%s' has been saved.") % (sname,) ,
				   type="ok")
    except:
	window = MessageWindow(_("Error Saving Screenshot"), 
			       _("An error occurred while saving "
				 "the screenshot.  If this occurred "
				 "during package installation, you may need "
				 "to try several times for it to succeed."),
			       type="warning")

		
def handleShiftPrintScrnRelease (window, event):
    if (event.keyval == gtk.keysyms.Print and event.state & gtk.gdk.SHIFT_MASK):
	takeScreenShot()
	    
	    
	

#
# HACK to make treeview work
# 
 
def setupTreeViewFixupIdleHandler(view, store):
    id = {}
    id["id"] = gtk.idle_add(scrollToIdleHandler, (view, store, id))

def scrollToIdleHandler((view, store, iddict)):
    if not view or not store or not iddict:
	return

    try:
	id = iddict["id"]
    except:
	return
    
    selection = view.get_selection()
    if not selection:
	return
    
    model, iter = selection.get_selected()
    if not iter:
	return

    path = store.get_path(iter)
    col = view.get_column(0)
    view.scroll_to_cell(path, col, gtk.TRUE, 0.5, 0.5)

    if id:
	gtk.idle_remove(id)

# setup globals
def processEvents():
    gtk.gdk.flush()
    while gtk.events_pending():
        gtk.main_iteration(gtk.FALSE)

def partedExceptionWindow(exc):
    # if our only option is to cancel, let us handle the exception
    # in our code and avoid popping up the exception window here.
    if exc.options == parted.EXCEPTION_CANCEL:
        return parted.EXCEPTION_UNHANDLED
    log("parted exception: %s: %s" %(exc.type_string,exc.message))
    print exc.type_string
    print exc.message
    print exc.options
    win = gtk.Dialog(exc.type_string, mainWindow, gtk.DIALOG_MODAL)
    addFrame(win)
    win.set_position(gtk.WIN_POS_CENTER)
    label = WrappingLabel(exc.message)
    win.vbox.pack_start (label)
    numButtons = 0
    buttonToAction = {}
    
    exflags = ((parted.EXCEPTION_FIX, N_("Fix")),
             (parted.EXCEPTION_YES, N_("Yes")),
             (parted.EXCEPTION_NO, N_("No")),
             (parted.EXCEPTION_OK, N_("OK")),
             (parted.EXCEPTION_RETRY, N_("Retry")),
             (parted.EXCEPTION_IGNORE, N_("Ignore")),
             (parted.EXCEPTION_CANCEL, N_("Cancel")))
    for flag, string in exflags:
        if exc.options & flag:
            win.add_button(_(string), flag)
    win.show_all()
    rc = win.run()
    win.destroy()
    return rc

def widgetExpander(widget, growTo=None):
    widget.connect("size-allocate", growToParent, growTo)

def growToParent(widget, rect, growTo=None):
    return
    if not widget.parent:
        return
    ignore = widget.__dict__.get("ignoreEvents")
    if not ignore:
        if growTo:
            x, y, width, height = growTo.get_allocation()
            widget.set_size_request(width, -1)
        else:
            widget.set_size_request(rect.width, -1)
        widget.ignoreEvents = 1
    else:
        widget.ignoreEvents = 0

_busyCursor = 0

def setCursorToBusy(process=1):
    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
    root.set_cursor(cursor)
    if process:
        processEvents()

def setCursorToNormal():
    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
    root.set_cursor(cursor)

def rootPushBusyCursor(process=1):
    global _busyCursor
    _busyCursor += 1
    if _busyCursor > 0:
	setCursorToBusy(process)

def rootPopBusyCursor():
    global _busyCursor
    _busyCursor -= 1
    if _busyCursor <= 0:
	setCursorToNormal()

def getBusyCursorStatus():
    global _busyCursor
    
    return _busyCursor

class MnemonicLabel(gtk.Label):
    def __init__(self, text="", alignment = None):
        gtk.Label.__init__(self, "")
        self.set_text_with_mnemonic(text)
        if alignment is not None:
            apply(self.set_alignment, alignment)

class WrappingLabel(gtk.Label):
    def __init__(self, label=""):
        gtk.Label.__init__(self, label)
        self.set_line_wrap(gtk.TRUE)
        self.ignoreEvents = 0
#        self.set_size_request(-1, 1)
        widgetExpander(self)

def titleBarMousePressCB(widget, event, data):
    if event.type & gtk.gdk.BUTTON_PRESS:
	data["state"] = 1
	data["button"] = event.button
	data["deltax"] = event.x
	data["deltay"] = event.y
	
def titleBarMouseReleaseCB(widget, event, data):
    if data["state"] and event.button == data["button"]:
	data["state"] = 0
	data["button"] = 0
	data["deltax"] = 0
	data["deltay"] = 0

def titleBarMotionEventCB(widget, event, data):
    if data["state"]:
	newx = event.x_root-data["deltax"]
	newy = event.y_root-data["deltay"]
	if newx < 0:
	    newx = 0
	if newy < 0:
	    newy = 0
	(w, h) = data["window"].get_size()
	if (newx+w) > gtk.gdk.screen_width():
	    newx = gtk.gdk.screen_width() - w
	if (newy+20) > (gtk.gdk.screen_height()):
	    newy = gtk.gdk.screen_height() - 20

	data["window"].move(int(newx), int(newy))

def addFrame(dialog, title=None, showtitle = 1):
    # We don't add a Frame in rootpath mode, as we almost certainly have a window manager
    contents = dialog.get_children()[0]
    dialog.remove(contents)
    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_OUT)
    box = gtk.VBox()
    try:
	if title is None:
	    title = dialog.get_title()

	if title and not flags.rootpath:
	    data = {}
	    data["state"] = 0
	    data["button"] = 0
	    data["deltax"] = 0
	    data["deltay"] = 0
	    data["window"] = dialog
	    eventBox = gtk.EventBox()
	    eventBox.connect("button-press-event", titleBarMousePressCB, data)
	    eventBox.connect("button-release-event", titleBarMouseReleaseCB, data)
	    eventBox.connect("motion-notify-event", titleBarMotionEventCB,data)
	    titleBox = gtk.HBox(gtk.FALSE, 5)
	    eventBox.add(titleBox)
	    eventBox.modify_bg(gtk.STATE_NORMAL,
                               eventBox.rc_get_style().bg[gtk.STATE_SELECTED])
            if showtitle:
                titlelbl = gtk.Label("")
                titlelbl.set_markup("<b>"+_(title)+"</b>")
                titlelbl.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse ("white"))
                titlelbl.set_property("ypad", 4)
                titleBox.pack_start(titlelbl)
            else:
                s = gtk.Label("")
                titleBox.pack_start(s)
	    box.pack_start(eventBox, gtk.FALSE, gtk.FALSE)
        elif flags.rootpath:
            dialog.set_title (title)
    except:
	pass
    
    frame2=gtk.Frame()
    frame2.set_shadow_type(gtk.SHADOW_NONE)
    frame2.set_border_width(4)
    frame2.add(contents)
    box.pack_start(frame2, gtk.TRUE, gtk.TRUE, padding=5)
    frame.add(box)
    frame.show()
    dialog.add(frame)

    # make screen shots work
    dialog.connect ("key-release-event", handleShiftPrintScrnRelease)


class WaitWindow:
    def __init__(self, title, text):
        if flags.rootpath:
            self.window = gtk.Window()
            self.window.set_decorated(False)
            # FIXME: we should really call set_transient_for
        else:
            self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.set_title(title)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_modal(gtk.TRUE)
        label = WrappingLabel(text)
        box = gtk.Frame()
        box.set_border_width(10)
        box.add(label)
        box.set_shadow_type(gtk.SHADOW_NONE)
        self.window.add(box)
        addFrame(self.window, showtitle = 0)
	self.window.show_all()
        rootPushBusyCursor()
            
    def pop(self):
        self.window.destroy()
        rootPopBusyCursor()

class ProgressWindow:
    def __init__(self, title, text, total):
        if flags.rootpath:
            self.window = gtk.Window()
            self.window.set_decorated(False)
            # FIXME: we should really call set_transient_for
            def no_delete (window, event):
                return True
            self.window.connect('delete-event', no_delete)
        else:
            self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.set_title (title)
        self.window.set_position (gtk.WIN_POS_CENTER)
        self.window.set_modal (gtk.TRUE)
        box = gtk.VBox (gtk.FALSE, 5)
        box.set_border_width (10)

        label = WrappingLabel (text)
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, gtk.FALSE)
        
        self.total = total
	self.progress = gtk.ProgressBar ()
        box.pack_start (self.progress, gtk.TRUE)
        self.window.add(box)

        addFrame(self.window, showtitle = 0)
	self.window.show_all ()
        rootPushBusyCursor()

    def set (self, amount):
	# only update widget if we've changed by 5%
	curval = self.progress.get_fraction()
	newval = float (amount) / self.total
	if newval < 0.998:
	    if (newval - curval) < 0.05 and newval > curval:
		return
	self.progress.set_fraction (newval)
        processEvents ()        
    
    def pop(self):
        self.window.destroy ()
        rootPopBusyCursor()

class ExceptionWindow:
    def __init__ (self, text):
        try:
            floppyDevices = 0
            for dev in kudzu.probe(kudzu.CLASS_FLOPPY, kudzu.BUS_UNSPEC,
                                   kudzu.PROBE_ALL):
                if not dev.detached:
                    floppyDevices = floppyDevices + 1
        except:
            floppyDevices = 0

        win = gtk.Dialog("Exception Occured", mainWindow, gtk.DIALOG_MODAL)
        win.add_button("_Debug", 0)
        if floppyDevices > 0 or DEBUG:
            win.add_button("_Save to floppy", 1)
        win.add_button('gtk-ok', 2)
        buffer = gtk.TextBuffer(None)
        buffer.set_text(text)
        textbox = gtk.TextView()
        textbox.set_buffer(buffer)
        textbox.set_property("editable", gtk.FALSE)
        textbox.set_property("cursor_visible", gtk.FALSE)
        sw = gtk.ScrolledWindow ()
        sw.add (textbox)
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        hbox = gtk.HBox (gtk.FALSE)

        if floppyDevices > 0:
            info = WrappingLabel(exceptionText)
        else:
            info = WrappingLabel(exceptionTextNoFloppy)
            
        info.set_size_request (400, -1)

        hbox.pack_start (sw, gtk.TRUE)
        win.vbox.pack_start (info, gtk.FALSE)            
        win.vbox.pack_start (hbox, gtk.TRUE)
        win.set_size_request (500, 300)
        win.set_position (gtk.WIN_POS_CENTER)
        addFrame(win)
        win.show_all ()
        self.window = win
        self.rc = self.window.run ()
        
    def getrc (self):
        # I did it this way for future expantion
        # 0 is debug
        if self.rc == 0:
            try:
                # switch to VC1 so we can debug
                isys.vtActivate (1)
            except SystemError:
                pass
            return 1
        # 1 is save
        if self.rc == 1:
            return 2
        # 2 is OK
        elif self.rc == 2:
            return 0

class MessageWindow:
    def getrc (self):
        return self.rc
    
    def __init__ (self, title, text, type="ok", default=None, custom_buttons=None, custom_icon=None):
        if flags.autostep:
            self.rc = 1
            return
        self.rc = None
	docustom = 0
        if type == 'ok':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_INFO
        elif type == 'warning':
            buttons = gtk.BUTTONS_OK
            style = gtk.MESSAGE_WARNING
        elif type == 'okcancel':
            buttons = gtk.BUTTONS_OK_CANCEL
            style = gtk.MESSAGE_WARNING
        elif type == 'yesno':
            buttons = gtk.BUTTONS_YES_NO
            style = gtk.MESSAGE_QUESTION
	elif type == 'custom':
	    docustom = 1
	    buttons = gtk.BUTTONS_NONE
	    style = gtk.MESSAGE_QUESTION

	if custom_icon == "warning":
	    style = gtk.MESSAGE_WARNING
	elif custom_icon == "question":
	    style = gtk.MESSAGE_QUESTION
	elif custom_icon == "error":
	    style = gtk.MESSAGE_ERROR
	elif custom_icon == "info":
	    style = gtk.MESSAGE_INFO

	dialog = gtk.MessageDialog(mainWindow, 0, style, buttons, text)

	if docustom:
	    rid=0
	    for button in custom_buttons:
		if button == _("Cancel"):
		    tbutton = "gtk-cancel"
		else:
		    tbutton = button

		widget = dialog.add_button(tbutton, rid)
		rid = rid + 1

            defaultchoice = rid - 1
	else:
	    if default == "no":
                defaultchoice = 0
	    elif default == "yes" or default == "ok":
                defaultchoice = 1
	    else:
                defaultchoice = 0

        addFrame(dialog, title=title)
        dialog.set_position (gtk.WIN_POS_CENTER)
        dialog.set_default_response(defaultchoice)
        dialog.show_all ()

	# XXX - Messy - turn off busy cursor if necessary
	busycursor = getBusyCursorStatus()
	setCursorToNormal()
        rc = dialog.run()

        if rc == gtk.RESPONSE_OK or rc == gtk.RESPONSE_YES:
            self.rc = 1
        elif (rc == gtk.RESPONSE_CANCEL or rc == gtk.RESPONSE_NO
            or rc == gtk.RESPONSE_CLOSE):
            self.rc = 0
	elif rc == gtk.RESPONSE_DELETE_EVENT:
	    self.rc = 0
	else:
	    self.rc = rc
        dialog.destroy()

	# restore busy cursor
	if busycursor:
	    setCursorToBusy()
    
class InstallInterface:
    def __init__ (self):
        # figure out if we want to run interface at 800x600 or 640x480
        if gtk.gdk.screen_width() >= 800:
            self.runres = "800x600"
        else:
            self.runres = "640x480"

    def __del__ (self):
        pass

    def shutdown (self):
	pass

    def setPackageProgressWindow (self, ppw):
        self.ppw = ppw

    def waitWindow (self, title, text):
	return WaitWindow (title, text)

    def progressWindow (self, title, text, total):
	return ProgressWindow (title, text, total)

    def packageProgressWindow (self, total, totalSize):
        self.ppw.setSizes (total, totalSize)
        return self.ppw

    def messageWindow(self, title, text, type="ok", default = None,
		     custom_buttons=None,  custom_icon=None):
        rc = MessageWindow (title, text, type, default,
			    custom_buttons, custom_icon).getrc()
        return rc

    def exceptionWindow(self, title, text):
        print text
        win = ExceptionWindow (text)
        return win.getrc ()

    def kickstartErrorWindow(self, text):
        s = _("The following error was found while parsing your "
              "kickstart configuration:\n\n%s") %(text,)
        return self.messageWindow(_("Error Parsing Kickstart Config"),
                                  s,
                                  type = "custom",
                                  custom_buttons = [_("_Reboot")],
                                  custom_icon = "error")

    def dumpWindow(self):
        window = MessageWindow("Save Crash Dump", 
                               _("Please insert a floppy now. All contents "
                                 "of the disk will be erased, so please "
                                 "choose your diskette carefully."),
                               "okcancel")
        rc = window.getrc()
	return not rc

    def getBootdisk (self):
        return None

    def run(self, id, dispatch, configFileData):
##         from xkb import XKB
##         kb = XKB()

	self.dispatch = dispatch

        # XXX users complain when the keypad doesn't work for input.
##         if 0 and flags.setupFilesystems:
##             try:
##                 kb.setMouseKeys (1)
##             except SystemError:
##                 pass

        # XXX x_already_set is a hack
        if id.keyboard and not id.x_already_set:
            id.keyboard.activate()
## 	    info = id.keyboard.getXKB()
## 	    if info:
##                 (rules, model, layout, variant, options) = info
##                 kb.setRule (model, layout, variant, "complete")

        id.fsset.registerMessageWindow(self.messageWindow)
        id.fsset.registerProgressWindow(self.progressWindow)
        id.fsset.registerWaitWindow(self.waitWindow)
        parted.exception_set_handler(partedExceptionWindow)

	lang = id.instLanguage.getCurrent()
	lang = id.instLanguage.getLangNick(lang)
        self.icw = InstallControlWindow (self, self.dispatch, lang)
        self.icw.run (self.runres, configFileData)

class TextViewBrowser(gtk.TextView):
    def __init__(self):
        self.hadj = None
        self.vadj = None

        gtk.TextView.__init__(self)
        self.set_property('editable', gtk.FALSE)
        self.set_property('cursor_visible', gtk.FALSE)
        self.set_left_margin(10)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.connect('set-scroll-adjustments', self.cacheAdjustments)

    def swallowFocus(self, *args):
        self.emit_stop_by_name('focus-in-event')        
        
    def cacheAdjustments(self, view, hadj, vadj):
        self.hadj = hadj
        self.vadj = vadj

    def moveCursor(self, view, step, count, extend_selection):
        if step == gtk.MOVEMENT_DISPLAY_LINES:
            if count == -1 and self.vadj != None:
                self.vadj.value = max(self.vadj.value - self.vadj.step_increment,
                                      self.vadj.lower)
                self.vadj.value_changed()
            elif count == 1 and self.vadj != None:
                self.vadj.value = min(self.vadj.value + self.vadj.step_increment - 1,
                                      self.vadj.upper - self.vadj.page_increment - 1)
                self.vadj.value_changed()
        elif step == gtk.MOVEMENT_PAGES:
            if count == -1 and self.vadj != None:
                self.vadj.value = max(self.vadj.value - self.vadj.page_increment,
                                      self.vadj.lower)
                self.vadj.value_changed()
            elif count == 1 and self.vadj != None:
                self.vadj.value = min(self.vadj.value + self.vadj.page_increment - 1,
                                      self.vadj.upper - self.vadj.page_increment - 1)
                self.vadj.value_changed()

        self.emit_stop_by_name ('move-cursor')

    
class InstallControlWindow:
    def setLanguage (self, locale):
	self.langSearchPath = expandLangs(locale) + ['C']
        
	if not self.__dict__.has_key('window'): return

        self.reloadRcQueued = 1

        # need to reload our widgets
        self.setLtR()
	self.loadReleaseNotes()

        # reload the glade file, although we're going to keep our toplevel
        self.loadGlade()
        win = self.mainxml.get_widget("mainWindow")
        win.hide()

        # gtk reparenting leaves us with non-working buttons, so
        # do our own reparenting per the FAQ
        orig = self.window.get_child()
        child = win.get_child()
        win.remove(child)
        orig.hide() # don't flicker!
        self.window.remove(orig)
        self.window.add(child)
        
        self.createWidgets()
        self.connectSignals()

    def setLtR(self):
        ltrrtl = gettext.dgettext("gtk20", "default:LTR")
        if ltrrtl == "default:RTL":
            gtk.widget_set_default_direction (gtk.TEXT_DIR_RTL)
        elif ltrrtl == "default:LTR":
            gtk.widget_set_default_direction (gtk.TEXT_DIR_LTR)
        else:
            log("someone didn't translate the ltr bits right: %s" %(ltrrtl,))
            gtk.widget_set_default_direction (gtk.TEXT_DIR_LTR)            
        
    def prevClicked (self, *args):
        ics = self.currentWindow.getICS()
        if not ics.getPrevEnabled():
            return
        
	try:
	    self.currentWindow.getPrev ()
	except StayOnScreen:
	    return

	self.dispatch.gotoPrev()
	self.dir = -1

        self.setScreen ()

    def nextClicked (self, widget, *args):
        ics = self.currentWindow.getICS()
        if not ics.getNextEnabled():
            return
        
	try:
	    rc = self.currentWindow.getNext ()
	except StayOnScreen:
	    return

	self.dispatch.gotoNext()
	self.dir = 1

        self.setScreen ()

    def loadReleaseNotes(self):
 	langList = self.langSearchPath + [ "" ]
	suffixList = []        
 	for lang in langList:
 	    if lang:
                 suffixList.append("-%s.html" % (lang,))
                 suffixList.append(".%s" % (lang,))
            else:
                 # XXX hack to work around #116170
                 suffixList.append("-en.html")
                 suffixList.append("-en")
                 
                 suffixList.append(".html")
                 suffixList.append("")

	for suffix in suffixList:
	    fn = "RELEASE-NOTES%s" % (suffix,)
	    try:
		tmpfile = self.dispatch.method.getFilename(fn, destdir="/tmp", retry=0)

		if tmpfile is None:
		    continue

		file = open(tmpfile, "r")
		self.releaseNotesContents = file.read()
		file.close()

		# deal with stupid urllib2 creating a zero length file
		# when the specified FTP URL doesnt exist
		if len(self.releaseNotesContents) < 1:
		    self.releaseNotesContents = None
		    continue
		
	    except:
		continue

	    if suffix.endswith('.html'):
		self.releaseNotesType="html"
	    else:
		self.releaseNotesType="text"

	    return

	self.releaseNotesContents=_("Release notes are missing.\n")
	self.releaseNotesType="text"

    #
    # cant use traditional signals and SIGCHLD to catch viewer exitting,
    # so instead we just check occasionally to see if child process still
    # around
    #
    def releaseNotesViewerPollExitCB(self, data):
	# dont wait if we arent running a viewer
	if self.releaseNotesViewerPid is None:
	    log("Calling releaseNotesViewerPollExitCB but no release viewer running!")
	    return gtk.TRUE

	# see if release notes viewer has exitted
	still_running = 1
	try:
	    (pid, status) = os.waitpid(self.releaseNotesViewerPid, os.WNOHANG)

	    if pid and os.WIFEXITED(status):
		still_running = 0
	except OSError, (eno, msg):
	    if eno == errno.ECHILD:
		still_running = 0
	    else:
		log("In releaseNotesViewerPollExitCB got error %s: %s", eno, msg)
	except:
	    log("In releaseNotesViewerPollExitCB got unknown exception waiting %s: %s")
	    
    
	if not still_running:
	    self.releaseNotesViewerPid = None
	    gtk.timeout_remove(self.releaseNotesViewerIdleID)
            self.mainxml.get_widget("buttonBar").set_sensitive(gtk.TRUE)
	    self.releaseNotesModalDummy.destroy()
	    
	    return gtk.FALSE
	else:
	    return gtk.TRUE

    # see if we need to start release notes viewer
    # needed because sometimes we get a callback to start viewer
    # when we are in an rpm callback inside the chroot and cannot
    # run the release notes program (sigh)
    def releaseNotesPollStartViewerCB(self, data):
	if self.releaseNotesStartViewer:
	    # turn off so we dont start multiple ones
	    self.releaseNotesStartViewer = 0

	    # make a 0 by 0 modal dialog so you cant interact with installer
	    # while release notes are up
	    self.releaseNotesModalDummy = gtk.Dialog(flags=gtk.DIALOG_MODAL)
	    self.releaseNotesModalDummy.set_size_request(0, 0)
	    self.releaseNotesModalDummy.set_decorated(gtk.FALSE)
	    self.releaseNotesModalDummy.show_all()
	    processEvents()
	    
	    # try to run it
	    rc = self.runReleaseNotesViewer()
	    if rc:
		# failed to run, note we havent started it yet
		self.releaseNotesModalDummy.destroy()
		self.releaseNotesStartViewerAttempts += 1
		if self.releaseNotesStartViewerAttempts > 15:
		    log("Giving up trying to run viewer!")
		    gtk.timeout_remove(self.releaseNotesStartViewerIdleID)
		    self.releaseNotesStartViewer = 0
		    self.releaseNotesStartViewerAttempts = 0
		    setCursorToNormal()
		else:
		    self.releaseNotesStartViewer = 1
	    else:
		# started viewer succesfully, remove idle handler
		gtk.timeout_remove(self.releaseNotesStartViewerIdleID)
	    
	return gtk.TRUE
		

    #
    # when user clicks on release notes button we queue a request to start
    # the release notes viewer. The idle handler we setup will try to
    # start the viewer when it is called. If we happen to be in an RPM
    # callback during package installation and are in the chroot we cannot
    # run the viewer.  The idle handler will just keep trying to start
    # viewer until it gets called outside the chroot environment.
    #
    # Yes this is icky.
    #
    def releaseNotesButtonClicked (self, widget):
	# see if release notes are running
	if self.releaseNotesViewerPid is not None:
	    log("Viewer already present, pid = %s",self.releaseNotesViewerPid)
	    return

	if self.releaseNotesStartViewer:
	    log("Already queued request to start a viewer")
	    return
	
	self.releaseNotesStartViewerAttempts = 0
	self.releaseNotesStartViewer = 1
	self.releaseNotesStartViewerIdleID = gtk.timeout_add(250, self.releaseNotesPollStartViewerCB, None)

	# we make cursor busy, on assumption when viewer app runs it will
	# make it normal
	setCursorToBusy()
	

    def runReleaseNotesViewer(self):
	if self.releaseNotesContents is not None:
	    fn = "/tmp/relnotes." + self.releaseNotesType
	    if not os.access(fn, os.R_OK):
		ofile = open(fn, "w+")
		ofile.write(self.releaseNotesContents)
		ofile.close()

	    # HACK to make release notes to work in test mode
	    if os.access("iw/release_notes_viewer_gui.py", os.X_OK):
		path = ("iw/release_notes_viewer_gui.py",)
	    else:
		path = ("/usr/lib/anaconda/iw/release_notes_viewer_gui.py",)

	    # if no viewer present then just ignore click
	    if not os.access(path[0], os.X_OK):
		log("Viewer missing at %s - ignoring", path[0])
		return 1
	    
	    args =(fn,)
	    
	    child = os.fork()
	    if (child == 0):
		# close unneeded fd's
		for i in range(3,255):
		    try:
			os.close(i)
		    except:
			pass
		    
		os.execv(path[0], path + args)

	    # we are going to check several times a second to see if
	    # release notes viewer has exited so we can restore button
	    # bar sensitivity
	    #
	    # NOTE we cant use a signal handler for SIGCHLD because the
	    # python interpretter cannot act on signals reliably while inside
	    # the gtk main loop.
	    #
            self.releaseNotesViewerIdleID =  gtk.timeout_add(50, self.releaseNotesViewerPollExitCB, None)
	    self.releaseNotesViewerPid = child
	    
	    #desensitize button bar at bottom of screen
            self.mainxml.get_widget("buttonBar").set_sensitive(gtk.FALSE)

	    return 0
	else:
	    win = MessageWindow(_("Warning"),
			   _("The release notes are missing."),
			    type="custom", custom_icon="warning",
			    custom_buttons=[_("OK")])

	    return 1

    def helpClicked (self, *args):
        if self.displayHelp:
            self.displayHelp = False
            self.mainxml.get_widget("hideHelpButton").hide()
            self.mainxml.get_widget("showHelpButton").show()
            self.mainxml.get_widget("showHelpButton").grab_focus()

            self.mainxml.get_widget("help").hide_all()
            self.mainxml.get_widget("mainTable").set_homogeneous(False)
        else:
            self.displayHelp = True
            self.mainxml.get_widget("showHelpButton").hide()
            self.mainxml.get_widget("hideHelpButton").show()
            self.mainxml.get_widget("hideHelpButton").grab_focus()            

            self.mainxml.get_widget("help").show_all()
            self.mainxml.get_widget("mainTable").set_homogeneous(True)

            self.refreshHelp()

    def debugClicked (self, *args):
        try:
            # switch to VC1 so we can debug
            isys.vtActivate (1)
        except SystemError:
            pass
        import pdb
        try:
            pdb.set_trace()
        except:
            sys.exit(-1)
        try:
            # switch back
            isys.vtActivate (7)
        except SystemError:
            pass
        
    def refreshHelp(self):
        buffer = htmlbuffer.HTMLBuffer()
        ics = self.currentWindow.getICS()
        buffer.feed(ics.getHTML(self.langSearchPath))
        textbuffer = buffer.get_buffer()
        self.help.set_buffer(textbuffer)
        # scroll to the top.  Do this with a mark so it's done in the idle loop
        iter = textbuffer.get_iter_at_offset(0)
        mark = textbuffer.create_mark("top", iter, gtk.FALSE)
        self.help.scroll_to_mark(mark, 0.0, gtk.FALSE, 0.0, 0.0)

    def handleRenderCallback(self):
        self.currentWindow.renderCallback()
        if flags.autostep:
	    if flags.autoscreenshot:
		# let things settle down graphically
		processEvents()
		time.sleep(1)
		takeScreenShot()
            self.nextClicked()
        else:
            gtk.idle_remove(self.handle)

    def setScreen (self):
	(step, args) = self.dispatch.currentStep()
	if step is None:
	    gtk.main_quit()
	    return

	if not stepToClass[step]:
	    if self.dir == 1:
		return self.nextClicked()
	    else:
		return self.prevClicked()
		
	(file, className) = stepToClass[step]
        newScreenClass = None
	s = "from %s import %s; newScreenClass = %s" % (file, className,
                                                        className)
        while 1:
            try:
                exec s
                break
            except ImportError, e:
                print e
                win = MessageWindow(_("Error!"),
                                   _("An error occurred when attempting "
                                     "to load an installer interface "
                                     "component.\n\nclassName = %s") % (className,),
                                    type="custom", custom_icon="warning",
                                    custom_buttons=[_("_Exit"),
                                                    _("_Retry")])
                if not win.getrc():
                    if flags.rootpath:
                        msg =  _("The installer will now exit...")
                        buttons = [_("_Exit")]
                    else:
                        msg =  _("Your system will now be rebooted...")
                        buttons = [_("_Reboot")]

                    MessageWindow(_("Rebooting System"),
                                  msg,
                                  type="custom",
                                  custom_icon="warning",
                                  custom_buttons=buttons)
                    sys.exit(0)
                
	ics = InstallControlState (self)
        ics.setPrevEnabled(self.dispatch.canGoBack())
        
	self.destroyCurrentWindow()
        self.currentWindow = newScreenClass(ics)

	new_screen = apply(self.currentWindow.getScreen, args)
	if not new_screen:
            return

        self.update (ics)

        self.installFrame.add(new_screen)
        self.installFrame.show_all()

	self.handle = gtk.idle_add(self.handleRenderCallback)

        if self.reloadRcQueued:
            self.window.reset_rc_styles()
            self.reloadRcQueued = 0

        if self.displayHelp:
            self.refreshHelp()
            
    def destroyCurrentWindow(self):
        children = self.installFrame.get_children ()
        if children:
            child = children[0]
            self.installFrame.remove (child)
            child.destroy ()
	self.currentWindow = None

    def update (self, ics):
        self.mainxml.get_widget("backButton").set_sensitive(ics.getPrevEnabled())
        self.mainxml.get_widget("nextButton").set_sensitive(ics.getNextEnabled())
        self.mainxml.get_widget("hideHelpButton").set_sensitive(ics.getHelpEnabled())
        self.mainxml.get_widget("showHelpButton").set_sensitive(ics.getHelpEnabled())

        if ics.getHelpEnabled() == gtk.FALSE and self.displayHelp:
            self.helpClicked()
        elif ics.getHelpEnabled() == gtk.TRUE and not self.displayHelp:
            self.helpClicked()
        if ics.getGrabNext():
            self.mainxml.get_widget("nextButton").grab_focus()

    def __init__ (self, ii, dispatch, locale):
        self.reloadRcQueued = 0
        self.ii = ii
        self.dispatch = dispatch
	self.setLanguage(locale)
        self.handle = None
        self.displayHelp = True

	self.releaseNotesContents = None
	self.releaseNotesType = None
	self.releaseNotesViewerPid = None
	self.releaseNotesStartViewer = 0
	self.releaseNotesStartViewerAttempts = 0

    def keyRelease (self, window, event):
        if ((event.keyval == gtk.keysyms.KP_Delete
             or event.keyval == gtk.keysyms.Delete)
            and (event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK))):
            gtk.main_quit()
            os._exit(0)
        # XXX hack: remove me when the accelerators work again.
        elif (event.keyval == gtk.keysyms.F12
              and self.currentWindow.getICS().getNextEnabled()):
            self.nextClicked()
	elif (event.keyval == gtk.keysyms.Print
	      and event.state & gtk.gdk.SHIFT_MASK):
	    takeScreenShot()

    def createWidgets (self):
        self.window.set_title(_("%s Installer") %(productName,))
        
        # FIXME: doesn't handle the lowres case
        # FIXME: and this is a hack...
        ics = InstallControlState (self)
        p = ics.readPixmapDithered("anaconda_header.png")
        if p is not None:
            i = self.mainxml.get_widget("headerImage")
            apply(i.set_from_pixmap, p.get_pixmap())
        else:
            print _("Unable to load title bar")

        if DEBUG:
            self.mainxml.get_widget("debugButton").set_visible(True)
        self.installFrame = self.mainxml.get_widget("installFrame")

        self.help = TextViewBrowser()
        self.mainxml.get_widget("helpView").add(self.help)
        self.help.show_all()

    def connectSignals(self):
        def noop (window, event):
            return True
        sigs = { "on_nextButton_clicked": self.nextClicked,
                 "on_rebootButton_clicked": self.nextClicked,                 
                 "on_backButton_clicked": self.prevClicked,
                 "on_hideHelpButton_clicked": self.helpClicked,
                 "on_showHelpButton_clicked": self.helpClicked,
                 "on_relnotesButton_clicked": self.releaseNotesButtonClicked,
                 "on_debugButton_clicked": self.debugClicked,
                 
                 "on_mainWindow_key_release_event": self.keyRelease,
                 "on_mainWindow_delete_event": noop,
                 }
        self.mainxml.signal_autoconnect(sigs)

    def loadGlade(self):
        self.mainxml = gtk.glade.XML("anaconda.glade", domain="anaconda")

    def setup_window (self, runres):
        self.setLtR()
	self.loadReleaseNotes()

        self.loadGlade()
        self.window = self.mainxml.get_widget("mainWindow")

        self.createWidgets()
        self.connectSignals()

        self.setScreen()
        self.window.show()
        splashScreenPop()
            
    def busyCursorPush(self):
        rootPushBusyCursor()
        
    def busyCursorPop(self):
        rootPopBusyCursor()
        
    def run (self, runres, configFileData):
        self.configFileData = configFileData
        self.setup_window(runres)
        gtk.main()
            
class InstallControlState:
    def __init__ (self, cw):
        self.searchPath = ("/mnt/source/RHupdates",
                           "./", "/usr/share/anaconda/")
        self.cw = cw
        self.prevEnabled = gtk.TRUE
        self.nextEnabled = gtk.TRUE
        self.title = _("Install Window")
        self.html = ""
        self.htmlFile = None
        self.helpEnabled = gtk.TRUE
        self.grabNext = False

    def setTitle (self, title):
        self.title = title
        self.cw.update (self)
        
    def getTitle (self):
        return self.title

    def setPrevEnabled (self, value):
        if value == self.prevEnabled: return
        self.prevEnabled = value
        self.cw.update (self)

    def getPrevEnabled (self):
        return self.prevEnabled
    
    def setNextEnabled (self, value):
        if value != self.nextEnabled:
	    self.nextEnabled = value
	    self.cw.update (self)

    def getNextEnabled (self):
        return self.nextEnabled

    def setHelpButtonEnabled (self, value):
        if value == self.helpButtonEnabled: return
        self.helpButtonEnabled = value
        self.cw.update (self)

    def getHelpButtonEnabled (self):
        return self.helpButtonEnabled

    def findPixmap(self, file):
        for path in ("/mnt/source/RHupdates/pixmaps/",
                     "/mnt/source/RHupdates/",
                     "/tmp/updates/pixmaps/", "/tmp/updates/",
                     "/tmp/product/pixmaps/", "/tmp/product/",
                     "/usr/share/anaconda/pixmaps/", "pixmaps/",
                     "/usr/share/pixmaps/",
                     "/usr/share/anaconda/", ""):
            fn = path + file
            if os.access(fn, os.R_OK):
                return fn
        return None
        
    def readPixmap (self, file, height = None, width = None):
        fn = self.findPixmap(file)
        if not fn:
            log("unable to load %s", file)
            return None
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(fn)
        except RuntimeError, msg:
            log("unable to read %s: %s", file, msg)
            return None
        if (height is not None and width is not None
            and height != pixbuf.get_height()
            and width != pixbuf.get_width()):
            sclpix = pixbuf.scale_simple(height, width,
                                         gtk.gdk.INTERP_BILINEAR)
            p = gtk.Image()
            p.set_from_pixbuf(sclpix)
        else:
            source = gtk.IconSource()
            source.set_pixbuf(pixbuf)
            source.set_size(gtk.ICON_SIZE_DIALOG)
            source.set_size_wildcarded(gtk.FALSE)
            iconset = gtk.IconSet()
            iconset.add_source(source)
            p = gtk.image_new_from_icon_set(iconset, gtk.ICON_SIZE_DIALOG)
        return p

    def readPixmapDithered(self, file, height = None, width = None):
        fn = self.findPixmap(file)
        if not fn:
            log("unable to load %s", file)
            return None
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(fn)
        except RuntimeError, msg:
            log("unable to read %s: %s", file, msg)
            return None
        if (height is not None and width is not None
            and height != pixbuf.get_height()
            and width != pixbuf.get_width()):
            pixbuf = pixbuf.scale_simple(height, width,
                                         gtk.gdk.INTERP_BILINEAR)

        (pixmap, mask) = pixbuf.render_pixmap_and_mask()
        pixbuf.render_to_drawable(pixmap, gtk.gdk.GC(pixmap), 0, 0, 0, 0,
                                  pixbuf.get_width(), pixbuf.get_height(),
                                  gtk.gdk.RGB_DITHER_MAX, 0, 0)
        p = gtk.Image()
        p.set_from_pixmap(pixmap, mask)
        return p

    def readHTML (self, file):
        self.htmlFile = file

    def setHTML (self, text):
        self.html = text
        self.cw.update (self)

    def getHTML (self, langPath):
        text = None
        if self.htmlFile:
            file = self.htmlFile

            if self.cw.configFileData.has_key("helptag"):
                helpTag = "-%s" % (self.cw.configFileData["helptag"],)
            else:
                helpTag = ""

            arch = "-%s" % (iutil.getArch(),)
            tags = [ "%s%s" % (helpTag, arch), "%s" % (helpTag,),
                     "%s" % (arch,), "" ]

            found = 0
            for path in self.searchPath:
                if found:
                    break
                for lang in langPath + ['C']:
                    if found:
                        break
                    for tag in tags:
                        try:
                            text = open("%s/help/%s/s1-help-screens-%s%s.html"
                                        % (path, lang, file, tag)).read ()
                            found = 1
                            break
                        except IOError:
                            continue
                if text:
                    break

            if text:
                text = text.replace("@RHL@", productName)
                text = text.replace("@RHLVER@", productVersion)
                return text

            print "Unable to read %s help text" % (file,)

        return self.html
    
    def setScreenPrev (self):
        self.cw.prevClicked ()

    def setScreenNext (self):
        self.cw.nextClicked ()

    def setHelpEnabled (self, value):
        self.helpEnabled = value
        self.cw.update (self)

    def getHelpEnabled (self):
        return self.helpEnabled

    def setGrabNext (self, value):
        self.grabNext = value
        self.cw.update (self)

    def getGrabNext (self):
        return self.grabNext

    def getICW (self):
        return self.cw
