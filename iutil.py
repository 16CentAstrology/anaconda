#
# iutil.py - generic install utility functions
#
# Erik Troan <ewt@redhat.com>
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

import types, os, sys, isys, select, string, stat, signal, shutil
import os.path
import rhpl, rhpl.executil
import warnings
from rhpl.executil import getfd
from flags import flags

import logging
log = logging.getLogger("anaconda")

def getArch ():
    warnings.warn("iutil.getArch is deprecated.  Use rhpl.getArch instead.",
                  DeprecationWarning, stacklevel=2)
    return rhpl.getArch()

def execWithRedirect(command, argv, stdin = 0, stdout = 1, stderr = 2,	
		     searchPath = 0, root = '/', newPgrp = 0,
		     ignoreTermSigs = 0):
    if not searchPath and not os.access (root + command, os.X_OK):
	raise RuntimeError, command + " can not be run"

    childpid = os.fork()
    if childpid == 0:
        if (root and root != '/'): 
	    os.chroot (root)
	    os.chdir("/")

	if ignoreTermSigs:
	    signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	    signal.signal(signal.SIGINT, signal.SIG_IGN)

        stdin = getfd(stdin)
        if stdout == stderr:
            stdout = getfd(stdout)
            stderr = stdout
        else:
            stdout = getfd(stdout)
            stderr = getfd(stderr)

	if stdin != 0:
	    os.dup2(stdin, 0)
	    os.close(stdin)
	if stdout != 1:
	    os.dup2(stdout, 1)
	    if stdout != stderr:
		os.close(stdout)
	if stderr != 2:
	    os.dup2(stderr, 2)
	    os.close(stderr)

        try:
            if (searchPath):
                os.execvp(command, argv)
            else:
                os.execv(command, argv)
        except OSError:
            # let the caller deal with the exit code of 1.
            pass

	os._exit(1)

    if newPgrp:
	os.setpgid(childpid, childpid)
	oldPgrp = os.tcgetpgrp(0)
	os.tcsetpgrp(0, childpid)

    status = -1
    try:
        (pid, status) = os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg

    if newPgrp:
	os.tcsetpgrp(0, oldPgrp)

    return status

def execWithCapture(command, argv, searchPath = 0, root = '/', stdin = 0,
		    stderr = 2, catchfd = 1, closefd = -1):

    if not searchPath and not os.access (root + command, os.X_OK):
	raise RuntimeError, command + " can not be run"

    (read, write) = os.pipe()

    childpid = os.fork()
    if (not childpid):
        if (root and root != '/'): os.chroot (root)
	os.dup2(write, catchfd)
	os.close(write)
	os.close(read)

	if closefd != -1:
	    os.close(closefd)

	if stdin:
	    os.dup2(stdin, 0)
	    os.close(stdin)

        if stderr == sys.stdout:
            stderr = sys.stdout.fileno()
        else:
            stderr = getfd(stderr)

	if stderr != 2:
	    os.dup2(stderr, 2)
	    os.close(stderr)

	if (searchPath):
	    os.execvp(command, argv)
	else:
	    os.execv(command, argv)

	os._exit(1)

    os.close(write)

    rc = ""
    s = "1"
    while (s):
	select.select([read], [], [])
	s = os.read(read, 1000)
	rc = rc + s

    os.close(read)

    try:
        os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg

    return rc

def copyFile(source, to):
    warnings.warn("iutil.copyFile is deprecated.  Use shutil.copyfile instead.",
                  DeprecationWarning, stacklevel=2)
    shutil.copyfile(source, to)

# return size of directory (and subdirs) in kilobytes
def getDirSize(dir):
    def getSubdirSize(dir):
	# returns size in bytes
        mydev = os.lstat(dir)[stat.ST_DEV]

        dsize = 0
        for f in os.listdir(dir):
	    curpath = '%s/%s' % (dir, f)
	    sinfo = os.lstat(curpath)
            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += getSubdirSize(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]
            else:
                pass

        return dsize
    return getSubdirSize(dir)/1024

# this is in kilobytes - returns amount of RAM not used by /tmp
def memAvailable():
    tram = memInstalled()

    ramused = getDirSize("/tmp")
    if os.path.isdir("/tmp/ramfs"):
        ramused += getDirSize("/tmp/ramfs")

    return tram - ramused

# this is in kilobytes
def memInstalled():
    if not os.access('/proc/e820info', os.R_OK):
        f = open("/proc/meminfo", "r")
        lines = f.readlines()
        f.close()

        for l in lines:
            if l.startswith("MemTotal:"):
                fields = string.split(l)
                mem = fields[1]
                break
    else:
        f = open("/proc/e820info", "r")
        lines = f.readlines()
        mem = 0
        for line in lines:
            fields = string.split(line)
            if fields[3] == "(usable)":
                mem = mem + (string.atol(fields[0], 16) / 1024)

    return int(mem)

# try to keep 2.4 kernel swapper happy!
def swapSuggestion(quiet=0):
    mem = memInstalled()/1024
    mem = ((mem/16)+1)*16
    if not quiet:
	log.info("Detected %sM of memory", mem)
	
    if mem < 128:
        minswap = 96
        maxswap = 192
    else:
        if mem > 1000:
            minswap = 1000
            maxswap = 2000
        else:
            minswap = mem
            maxswap = 2*mem

    if not quiet:
	log.info("Swap attempt of %sM to %sM", minswap, maxswap)

    return (minswap, maxswap)

    
# this is a mkdir that won't fail if a directory already exists and will
# happily make all of the directories leading up to it. 
def mkdirChain(dir):
    try:
        os.makedirs(dir, 0755)
    except OSError, (errno, msg):
        log.error("could not create directory %s: %s" % (dir, msg))
        pass

def rmrf (path):
    warnings.warn("iutil.rmrf is deprecated.  Use shutil.rmtree instead.",
                  DeprecationWarning, stacklevel=2)
    shutil.rmtree(path)

def swapAmount():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("SwapTotal:"):
            fields = string.split(l)
            return int(fields[1])
    return 0
        
def copyDeviceNode(src, dest):
    """Copies the device node at src to dest by looking at the type of device,
    major, and minor of src and doing a new mknod at dest"""

    filestat = os.lstat(src)
    mode = filestat[stat.ST_MODE]
    if stat.S_ISBLK(mode):
        type = stat.S_IFBLK
    elif stat.S_ISCHR(mode):
        type = stat.S_IFCHR
    else:
        # XXX should we just fallback to copying normally?
        raise RuntimeError, "Tried to copy %s which isn't a device node" % (src,)

    isys.mknod(dest, mode | type, filestat.st_rdev)

# make the device-mapper control node
def makeDMNode(root="/"):
    major = minor = None

    for (fn, devname, val) in ( ("/proc/devices", "misc", "major"),
                                ("/proc/misc", "device-mapper", "minor") ):
        f = open(fn)
        lines = f.readlines()
        f.close()
        for line in lines:
            try:
                (num, dev) = line.strip().split(" ")
            except:
                continue
            if dev == devname:
                s = "%s = int(num)" %(val,)
                exec s
                break

#    print "major is %s, minor is %s" %(major, minor)
    if major is None or minor is None:
        return
    mkdirChain(root + "/dev/mapper")
    isys.mknod(root + "/dev/mapper/control", stat.S_IFCHR | 0600,
               isys.makedev(major, minor))

# make some miscellaneous character device nodes 
def makeCharDeviceNodes():
    for dev in ["input/event0", "input/event1", "input/event2", "input/event3"]:
        isys.makeDevInode(dev, "/dev/%s" % (dev,))

# make the device nodes for all of the drives on the system
def makeDriveDeviceNodes():
    import raid
    
    hardDrives = isys.hardDriveDict()
    for drive in hardDrives.keys():
        if drive.startswith("mapper"):
            continue
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

        if drive.startswith("hd"):
            num = 32
        elif drive.startswith("dasd"):
            num = 4
        else:
            num = 15

        if (drive.startswith("cciss") or drive.startswith("ida") or
            drive.startswith("rd") or drive.startswith("sx8")):
            sep = "p"
        else:
            sep = ""

        for i in range(1, num):
            dev = "%s%s%d" % (drive, sep, i)
            isys.makeDevInode(dev, "/dev/%s" % (dev,))

    cdroms = isys.cdromList()
    for drive in cdroms:
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

    for mdMinor in range(0, 32):
        md = "md%d" %(mdMinor,)
        isys.makeDevInode(md, "/dev/%s" %(md,))

    # make the node for the device mapper
    makeDMNode()
    
# this is disgusting and I feel very dirty
def hasiSeriesNativeStorage():
    if getArch() != "ppc":
        return

    f = open("/proc/modules", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if line.startswith("ibmsis"):
            return 1
        if line.startswith("ipr"):
            return 1

    return 0

# return the ppc machine variety type
def getPPCMachine():
    
    if getArch() != "ppc":
        return 0
    
    machine = rhpl.getPPCMachine()
    if machine is None:
        log.warning("Unable to find PowerPC machine type")
    elif machine == 0:
        log.warning("Unknown PowerPC machine type: %s" %(machine,))

    return machine

# return the pmac machine id
def getPPCMacID():
    machine = None
    
    if getArch() != "ppc":
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
      if line.find('machine') != -1:
        machine = line.split(':')[1]
        machine = machine.strip()
        return machine

    log.warning("No Power Mac machine id")
    return 0

# return the pmac generation
def getPPCMacGen():
    # XXX: should NuBus be here?
    pmacGen = ['OldWorld', 'NewWorld', 'NuBus']
    
    if getArch() != "ppc":
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    gen = None
    for line in lines:
      if line.find('pmac-generation') != -1:
        gen = line.split(':')[1]
        break

    if gen is None:
        log.warning("Unable to find pmac-generation")

    for type in pmacGen:
      if gen.find(type) != -1:
          return type

    log.warning("Unknown Power Mac generation: %s" %(gen,))
    return 0

# return if pmac machine is it an iBook/PowerBook
def getPPCMacBook():
    if getArch() != "ppc":
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if not string.find(string.lower(line), 'book') == -1:
        return 1
    return 0

def hasNX():
    """Convenience function to see if a machine supports the nx bit. We want
    to install an smp kernel if NX is present since NX requires PAE (#173245)"""
    if getArch() not in ("i386", "x86_64"):
        return False
    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if not line.startswith("flags"):
            continue
        # get the actual flags
        flags = line[:-1].split(":", 1)[1]
        # and split them
        flst = flags.split(" ")
        if "nx" in flst:
            return True
    return False
    

def writeRpmPlatform(root="/"):
    import rhpl.arch

    if flags.test:
        return
    if os.access("%s/etc/rpm/platform" %(root,), os.R_OK):
        return
    if not os.access("%s/etc/rpm" %(root,), os.X_OK):
        os.mkdir("%s/etc/rpm" %(root,))

    myarch = rhpl.arch.canonArch

    # now allow an override with rpmarch=i586 on the command line (#101971)
    f = open("/proc/cmdline", "r")
    buf = f.read()
    f.close()
    args = buf.split()
    for arg in args:
        if arg.startswith("rpmarch="):
            myarch = arg[8:]

    # now make the current install believe it, too
    rhpl.arch.canonArch = myarch            
        
    f = open("%s/etc/rpm/platform" %(root,), 'w+')
    f.write("%s-redhat-linux\n" %(myarch,))
    f.close()

    # FIXME: writing /etc/rpm/macros feels wrong somehow
    # temporary workaround for #92285
    if os.access("%s/etc/rpm/macros" %(root,), os.R_OK):
        return
    if not (myarch.startswith("ppc64") or
            myarch in ("s390x", "sparc64", "x86_64", "ia64")):
        return
    f = open("%s/etc/rpm/macros" %(root,), 'w+')
    f.write("%_transaction_color   3\n")
    f.close()
    
