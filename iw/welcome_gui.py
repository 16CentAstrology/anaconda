from gtk import *
from gnome.ui import *
from iw_gui import *
from translate import _, N_
import GdkImlib

class WelcomeWindow (InstallWindow):		

    windowTitle = N_("Welcome")
    htmlTag = "wel"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setGrabNext (1)

    def load_image(self, file):
        print file
        try:
            print ("/usr/share/anaconda/" + file)
            im = GdkImlib.Image("/usr/share/anaconda/" + file)
        except:
            try:
                im = GdkImlib.Image("" + file)
            except:
                print "Unable to load", file

        return im

    # WelcomeWindow tag="wel"
    def getScreen (self, configFileData):
        print configFileData
        
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)

        image = configFileData["WelcomeScreen"]

        im = self.load_image(image)
        
        if im:
            im.render ()
            box = GtkEventBox ()
            pix = im.make_pixmap ()
            style = box.get_style ().copy ()
            style.bg[STATE_NORMAL] = style.white
            box.set_style (style)
            box.add (pix)
            frame.add (box)

        return frame

class ReconfigWelcomeWindow (InstallWindow):		

    windowTitle = N_("Welcome")
    htmlTag = "welreconfig"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setNextEnabled (1)
	self.beingDisplayed = 0

    def getNext (self):
        if not self.beingDisplayed: return

        if self.cancelChoice.get_active():
            import sys

            print "Exitting"
            sys.exit(0)
        else:
            self.beingDisplay = 0
            return None

    # ReconfigWelcomeWindow tag="welreconfig"
    def getScreen (self):


	frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)

        box = GtkVBox (FALSE)
        box.set_border_width (5)
        frame.add (box)

        im = self.ics.readPixmap ("first-375.png")
        
        if im:
            im.render ()
            ebox = GtkEventBox ()
            pix = im.make_pixmap ()
            style = ebox.get_style ().copy ()
            style.bg[STATE_NORMAL] = style.white
            ebox.set_style (style)
            ebox.add (pix)
            box.pack_start (ebox, FALSE)

        label = GtkLabel(_("Would you like to configure your system?"))
	label.set_line_wrap(TRUE)
	label.set_alignment(0.0, 0.0)
	label.set_usize(400, -1)

        box.pack_start(label)
        
        radioBox = GtkVBox (FALSE)
	self.continueChoice = GtkRadioButton (None, _("Yes"))
	radioBox.pack_start(self.continueChoice, FALSE)
	self.cancelChoice = GtkRadioButton(
		self.continueChoice, _("No"))
	radioBox.pack_start(self.cancelChoice, FALSE)

	align = GtkAlignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)

	box.pack_start(align, TRUE, TRUE)
	box.set_border_width (5)
	self.beingDisplayed = 1

	return frame
    
