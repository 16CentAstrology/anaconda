#
# harddrive.py - Install method for hard drive installs
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


from comps import ComponentSet, HeaderList, HeaderListFromFile
from installmethod import InstallMethod, FileCopyException
from image import findIsoImages
import shutil
import os
import isys
import iutil
import rpm
import string
from rhpl.translate import _, cat, N_
from rhpl.log import log

FILENAME = 1000000

# Install from one or more iso images
class HardDriveInstallMethod(InstallMethod):
    def copyFileToTemp(self, filename):
        wasmounted = self.mediaIsMounted

        if not wasmounted:
            self.mountMedia(1)
        tmppath = self.getTempPath()
        path = tmppath + os.path.basename(filename)
        shutil.copy(self.tree + "/" + filename, path)

        if not wasmounted:
            self.umountMedia()
        
        return path

    # mounts disc image cdNum under self.tree
    def mountMedia(self, cdNum):
	if (self.mediaIsMounted):
	    raise SystemError, "trying to mount already-mounted iso image!"

	isoImage = self.isoDir + '/' + self.path + '/' + self.discImages[cdNum]

	isys.makeDevInode("loop3", "/tmp/loop3")
	isys.losetup("/tmp/loop3", isoImage, readOnly = 1)
	
	isys.mount("loop3", "/tmp/isomedia", fstype = 'iso9660', readOnly = 1);
	self.tree = "/tmp/isomedia/"
	self.mediaIsMounted = cdNum

    def umountMedia(self):
	if self.mediaIsMounted:
	    isys.umount(self.tree)
	    isys.makeDevInode("loop3", "/tmp/loop3")
	    isys.unlosetup("/tmp/loop3")
	    self.mediaIsMounted = 0

    def readCompsViaMethod(self, hdlist):
	self.mountMedia(1)
	fname = self.findBestFileMatch(self.tree, 'comps.xml')
	cs = ComponentSet(fname, hdlist)
	self.umountMedia()
	return cs

    def getFilename(self, h, timer, callback=None):
	if self.mediaIsMounted != h[1000002]:
	    self.umountMedia()
	    self.mountMedia(h[1000002])

	return self.tree + "/RedHat/RPMS/" + h[1000000]

    def readHeaders(self):
	self.mountMedia(1)
        if not os.access(self.tree + "/RedHat/base/hdlist", os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hl = HeaderListFromFile(self.tree + "/RedHat/base/hdlist")
	self.umountMedia()

	# Make sure all of the correct CD images are available
	for h in hl.values():
            import sys
	    if not self.discImages.has_key(h[1000002]):
		self.messageWindow(_("Error"),
			_("Missing ISO image for CD #%d, which is required for the "
			  "install.\n\nThe system will now reboot.") % h[1000002])
		sys.exit(0)

	return hl

    def mergeFullHeaders(self, hdlist):
	self.mountMedia(1)
        if not os.access(self.tree + "/RedHat/base/hdlist", os.R_OK):
            self.umountMedia()
            raise FileCopyException
	hdlist.mergeFullHeaders(self.tree + "/RedHat/base/hdlist2")
	self.umountMedia()

    def systemMounted(self, fsset, mntPoint, selected):
	self.mountMedia(1)
	    
    def systemUnmounted(self):
	self.umountMedia()

    def filesDone(self):
        # we're trying to unmount the source image at the end.  if it
        # fails, we'll reboot soon enough anyway
        try:
            self.umountMedia()
        except:
            log("unable to unmount media")

    def protectedPartitions(self):
        rc = []
        rc.append(self.device)
        return rc
    
    def __init__(self, device, type, path, messageWindow, rootPath):
	InstallMethod.__init__(self, rootPath)
	self.device = device
	self.path = path
	self.fstype = type
	self.fnames = {}
        self.mediaIsMounted = 0
	self.messageWindow = messageWindow

	# assumes that loader set this up properly as /tmp/isodir
        self.isoDir = "/tmp/hdimage"

	# Go ahead and poke through the directory looking for interesting
	# iso images
	self.discImages = findIsoImages(self.isoDir + '/' + self.path, messageWindow)
