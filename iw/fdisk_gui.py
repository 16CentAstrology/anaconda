from gtk import *
from iw_gui import *
from gnome.zvt import *
from translate import _
import isys
import os

class FDiskWindow (InstallWindow):		
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setTitle (_("fdisk"))
        ics.readHTML ("fdisk")

    def child_died (self, widget, button):
        self.windowContainer.remove (self.windowContainer.children ()[0])
        self.windowContainer.pack_start (self.buttonBox)
        button.set_state (STATE_NORMAL)
        try:
            os.remove ('/tmp/' + self.drive)
        except:
            # XXX fixme
            pass
        self.ics.readHTML ("fdisk")
        self.ics.setPrevEnabled (1)
        self.ics.setNextEnabled (1)
#        self.ics.setHelpEnabled (1)

    def button_clicked (self, widget, drive):
        zvt = ZvtTerm (80, 24)
        zvt.set_del_key_swap(TRUE)
        zvt.connect ("child_died", self.child_died, widget)
        self.drive = drive

	# free our fd's to the hard drive -- we have to 
	# fstab.rescanDrives() after this or bad things happen!
        if os.access("/sbin/fdisk", os.X_OK):
            path = "/sbin/fdisk"
        else:
            path = "/usr/sbin/fdisk"
        
	isys.makeDevInode(drive, '/tmp/' + drive)

        if zvt.forkpty() == 0:
            env = os.environ
            os.execve (path, (path, '/tmp/' + drive), env)
        zvt.show ()

        self.windowContainer.remove (self.buttonBox)
        self.windowContainer.pack_start (zvt)

#        self.ics.setHelpEnabled (0)
        self.ics.readHTML ("fdiskpart")
	self.ics.setPrevEnabled (0)
        self.ics.setNextEnabled (0)

    # FDiskWindow tag="fdisk"
    def getScreen (self, diskset):
        self.diskset = diskset
        
        self.windowContainer = GtkVBox (FALSE)
        self.buttonBox = GtkVBox (FALSE, 5)
        self.buttonBox.set_border_width (5)
        box = GtkVButtonBox ()
        label = GtkLabel (_("Select drive to run fdisk on"))

        for drive in self.diskset.driveList():
            button = GtkButton (drive)
            button.connect ("clicked", self.button_clicked, drive)
            box.add (button)

        self.buttonBox.pack_start (label, FALSE)
        self.buttonBox.pack_start (box, FALSE)
        self.windowContainer.pack_start (self.buttonBox)

        self.ics.setNextEnabled (1)

        return self.windowContainer
