# Install method for disk image installs (CD & NFS)

from comps import ComponentSet, HeaderListFromFile
from installmethod import InstallMethod
import iutil
import os
import isys
import time
import kudzu
import string
from translate import _
from log import log

class ImageInstallMethod(InstallMethod):

    def readComps(self, hdlist):
	return ComponentSet(self.tree + '/RedHat/base/comps', hdlist)

    def getFilename(self, h, timer):
	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	return HeaderListFromFile(self.tree + "/RedHat/base/hdlist")

    def mergeFullHeaders(self, hdlist):
	hdlist.mergeFullHeaders(self.tree + "/RedHat/base/hdlist2")

    def writeCleanupPath(self, f):
	isys.makeDevInode("loop0", "/tmp/loop0")
	f.write("umount /mnt/runtime\n")
	f.write("lounsetup /tmp/loop0\n")

    def __init__(self, tree):
	InstallMethod.__init__(self)
	self.tree = tree

class CdromInstallMethod(ImageInstallMethod):

    def systemUnmounted(self):
	if self.loopbackFile:
	    isys.makeDevInode("loop0", "/tmp/loop")
	    isys.lochangefd("/tmp/loop", 
			"%s/RedHat/base/stage2.img" % self.tree)
	    self.loopbackFile = None

    def systemMounted(self, fsset, chroot, selected):
	changeloop=0
	for p in selected:
	    if p[1000002] and p[1000002] > 1:
		changeloop=1
		break
	if changeloop == 0:
	    return

	self.loopbackFile = "%s%s%s" % (chroot,
                                        fsset.filesystemSpace(chroot)[0][0],
                                        "/rhinstall-stage2.img")

	try:
	    iutil.copyFile("%s/RedHat/base/stage2.img" % self.tree, 
			    self.loopbackFile,
			    (self.progressWindow, _("Copying File"),
			    _("Transferring install image to hard drive...")))
	except:
	    self.messageWindow(_("Error"),
		    _("An error occured transferring the install image "
		      "to your hard drive. You are probably out of disk "
		      "space."))
	    os.unlink(self.loopbackFile)
	    return 1

	isys.makeDevInode("loop0", "/tmp/loop")
	isys.lochangefd("/tmp/loop", self.loopbackFile)

    def getFilename(self, h, timer):
        if h[1000002] == None:
            log ("header for %s has no disc location tag, assuming it's"
                 "on the current CD", h[1000000])
        elif h[1000002] != self.currentDisc:
	    timer.stop()

	    key = ".disc%d-%s" % (self.currentDisc, iutil.getArch())
	    f = open("/mnt/source/" + key)
	    timestamp = f.readline()
	    f.close()

	    self.currentDisc = h[1000002]
	    isys.umount("/mnt/source")

	    done = 0
	    key = "/mnt/source/.disc%d-%s" % (self.currentDisc, iutil.getArch())

	    cdlist = []
	    for (dev, something, descript) in \
		    kudzu.probe(kudzu.CLASS_CDROM, kudzu.BUS_UNSPEC, 0):
		if dev != self.device:
		    cdlist.append(dev)

	    for dev in cdlist:
		try:
		    if not isys.mount(dev, "/mnt/source", fstype = "iso9660", 
			       readOnly = 1):
			if os.access(key, os.O_RDONLY):
			    f = open(key)
			    newStamp = f.readline()
			    f.close()
			    if newStamp == timestamp:
				done = 1

			if not done:
			    isys.umount("/mnt/source")
		except:
		    pass

	    if not done:
		isys.ejectCdrom(self.device)

	    while not done:
		self.messageWindow(_("Change CDROM"), 
		    _("Please insert disc %d to continue.") % self.currentDisc)

		try:
		    if isys.mount(self.device, "/mnt/source", 
				  fstype = "iso9660", readOnly = 1):
			time.sleep(3)
			isys.mount(self.device, "/mnt/source", 
				   fstype = "iso9660", readOnly = 1)
		    
		    if os.access(key, os.O_RDONLY):
			f = open(key)
			newStamp = f.readline()
			f.close()
			if newStamp == timestamp:
			    done = 1

		    if not done:
			self.messageWindow(_("Wrong CDROM"),
				_("That's not the correct Red Hat CDROM."))
			isys.umount("/mnt/source")
			isys.ejectCdrom(self.device)
		except:
		    self.messageWindow(_("Error"), 
			    _("The CDROM could not be mounted."))

	    timer.start()

	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def filesDone(self):
        if not self.loopbackFile: return

	try:
	    # this isn't the exact right place, but it's close enough
	    os.unlink(self.loopbackFile)
	except SystemError:
	    pass

    def writeCleanupPath(self, f):
	isys.makeDevInode("loop0", "/tmp/loop0")
	isys.makeDevInode(self.device, "/tmp/cdrom")
	f.write("umount /mnt/runtime\n")
	f.write("lounsetup /tmp/loop0\n")
	f.write("umount /mnt/source\n")
	f.write("eject /tmp/cdrom\n")

    def __init__(self, url, messageWindow, progressWindow):
	(self.device, tree) = string.split(url, "/", 1)
	self.messageWindow = messageWindow
	self.progressWindow = progressWindow
	self.currentDisc = 1
        self.loopbackFile = None
	ImageInstallMethod.__init__(self, "/" + tree)

class NfsInstallMethod(ImageInstallMethod):

    def __init__(self, tree):
	ImageInstallMethod.__init__(self, tree)
