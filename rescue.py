import upgrade
from snack import *
from text import WaitWindow, OkCancelWindow
from translate import _
import _balkan
import sys
import raid
import os
from log import log
import isys

class RescueInterface:

    def waitWindow(self, title, text):
	return WaitWindow(self.screen, title, text)

    def messageWindow(self, title, text, type = "ok"):
	if type == "ok":
	    ButtonChoiceWindow(self.screen, _(title), _(text),
			       buttons = [ _("OK") ])
	else:
	    return OkCancelWindow(self.screen, _(title), _(text))

    def __init__(self, screen):
	self.screen = screen

def runRescue(url, serial, mountroot):

    from fstab import NewtFstab

    fstab = None

    log.open (serial, 0, 0, 1)

    for file in [ "services", "protocols", "group" ]:
       os.symlink('/mnt/runtime/etc/' + file, '/etc/' + file)

    if (not mountroot):
	os.execv("/bin/sh", [ "-/bin/sh" ])

    try:
	fstab = NewtFstab(1, serial, 0, 0, None, None, None, 0, [], 0, 0,
			  requireBlockDevices = 0)
    except SystemError, text:
	print _("WARNING: no valid block devices were found.\n")
    except:
	print _("ERROR: unknown error encountered reading partition tables.\n")
	
    if not fstab:
	os.execv("/bin/sh", [ "-/bin/sh" ])

    # lets create some devices
    for drive in fstab.driveList():
	isys.makeDevInode(drive, "/dev/" + drive)
	
	for i in range(16):
	    if drive [:3] == "rd/" or drive [:4] == "ida/" or drive [:6] == "cciss/":
		dev = drive + 'p' + str (i + 1)
	    else:
		dev = drive + str (i + 1)

	    isys.makeDevInode(dev, "/dev/" + dev)

    screen = SnackScreen()
    intf = RescueInterface(screen)

    # go ahead and set things up for reboot
    if url[0:6] == "cdrom:" or url[0:4] == "nfs:":
	f = open("/tmp/cleanup", "w")

	isys.makeDevInode("loop0", "/tmp/loop0")
	f.write("umount /mnt/runtime\n")
	f.write("lounsetup /tmp/loop0\n")

	f.close()

    parts = upgrade.findExistingRoots(intf, fstab)

    if not parts:
	root = None
    elif len(parts) == 1:
	root = parts[0]
    else:
	height = min (len (parts), 12)
	if height == 12:
	    scroll = 1
	else:
	    scroll = 0

	partList = []
	for (drive, fs) in parts:
	    partList.append(drive)

	(button, choice) = \
	    ListboxChoiceWindow(screen, _("System to Rescue"),
				_("What partition holds the root partition "
				  "of your installation?"), partList, 
				[ _("OK"), _("Exit") ], width = 30,
				scroll = scroll, height = height,
				help = "multipleroot")

	if button == string.lower (_("Exit")):
	    root = None
	else:
	    root = parts[choice]

    rootmounted = 0
    if root:
	try:
	    upgrade.mountRootPartition(intf, root, fstab, '/mnt/sysimage', 
			       allowDirty = 1)
	    ButtonChoiceWindow(screen, _("Rescue"),
		_("Your system has been mounted under /mnt/sysimage.\n\n"
		  "Press <return> to get a shell. The system will reboot "
		  "automatically when you exit from the shell."),
		  [_("OK")] )
            rootmounted = 1
	except:
	    # This looks horrible, but all it does is catch every exception,
	    # and reraise those in the tuple check. This lets programming
	    # errors raise exceptions, while any runtime error will
	    # still result in a shell. 
	    (exc, val) = sys.exc_info()[0:2]
	    if exc in (IndexError, ValueError, SyntaxError):
		raise exc, val, sys.exc_info()[2]

	    ButtonChoiceWindow(screen, _("Rescue").
		_("An error occured trying to mount some or all of your "
		  "system. Some of it may be mounted under /mnt/sysimage.\n\n"
		  "Press <return> to get a shell. The system will reboot "
		  "automatically when you exit from the shell."),
		  [_("OK")] )
    else:
	ButtonChoiceWindow(screen, _("Rescue Mode"),
			   _("You don't have any Linux partitions. Press "
			     "return to get a shell. The system will reboot "
			     "automatically when you exit from the shell."),
			   [ _("Back") ], width = 50)

    screen.finish()

    if rootmounted:
        print
        print _("Your system is mounted under the /mnt/sysimage directory.")
        print

    os.execv("/bin/sh", [ "-/bin/sh" ])
