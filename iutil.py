#
# iutil.py - generic install utility functions
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, isys, string, stat
import os.path
from errno import *
import rhpl
import warnings
import subprocess
from flags import flags

import logging
log = logging.getLogger("anaconda")

## Run an external program and redirect the output to a file.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stdout The file descriptor to redirect stdout to.
# @param stderr The file descriptor to redirect stderr to.
# @param searchPath Should command be searched for in $PATH?
# @param root The directory to chroot to before running command.
# @return The return code of command.
def execWithRedirect(command, argv, stdin = 0, stdout = 1, stderr = 2,
                     searchPath = 0, root = '/'):
    def chroot ():
        os.chroot(root)

        if not searchPath and not os.access (command, os.X_OK):
            raise RuntimeError, command + " can not be run"

    argv = list(argv)
    if type(stdin) == type("string"):
        if os.access(stdin, os.R_OK):
            stdin = open(stdin)
        else:
            stdin = 0
    if type(stdout) == type("string"):
        stdout = open(stdout, "w")
    if type(stderr) == type("string"):
        stderr = open(stderr, "w")

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin, stdout=stdout,
                                stderr=stderr, preexec_fn=chroot, cwd=root)
        ret = proc.wait()
    except OSError, (errno, msg):
        errstr = "Error running %s: %s" % (command, msg)
        log.error (errstr)
        raise RuntimeError, errstr

    return ret

## Run an external program and capture standard out.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @return The output of command from stdout.
def execWithCapture(command, argv, stdin = 0, stderr = 2, root='/'):
    def chroot():
        os.chroot(root)

    argv = list(argv)
    if type(stdin) == type("string"):
        if os.access(stdin, os.R_OK):
            stdin = open(stdin)
        else:
            stdin = 0
    if type(stderr) == type("string"):
        stderr = open(stderr, "w")

    try:
        pipe = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                preexec_fn=chroot, cwd=root)
    except OSError, (errno, msg):
        log.error ("Error running " + command + ": " + msg)
        raise RuntimeError, "Error running " + command + ": " + msg

    rc = pipe.stdout.read()
    pipe.wait()
    return rc

## Run a shell.
def execConsole():
    try:
        proc = subprocess.Popen(["/bin/sh"])
        proc.wait()
    except OSError, (errno, msg):
        raise RuntimeError, "Error running /bin/sh: " + msg

## Get the size of a directory and all its subdirectories.
# @param dir The name of the directory to find the size of.
# @return The size of the directory in kilobytes.
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

## Get the amount of RAM not used by /tmp.
# @return The amount of available memory in kilobytes.
def memAvailable():
    tram = memInstalled()

    ramused = getDirSize("/tmp")
    if os.path.isdir("/tmp/ramfs"):
        ramused += getDirSize("/tmp/ramfs")

    return tram - ramused

## Get the amount of RAM installed in the machine.
# @return The amount of installed memory in kilobytes.
def memInstalled():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("MemTotal:"):
            fields = string.split(l)
            mem = fields[1]
            break

    return int(mem)

## Suggest the size of the swap partition that will be created.
# @param quiet Should size information be logged?
# @return A tuple of the minimum and maximum swap size, in megabytes.
def swapSuggestion(quiet=0):
    mem = memInstalled()/1024
    mem = ((mem/16)+1)*16
    if not quiet:
	log.info("Detected %sM of memory", mem)
	
    if mem <= 256:
        minswap = 256
        maxswap = 512
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

## Create a directory path.  Don't fail if the directory already exists.
# @param dir The directory path to create.
def mkdirChain(dir):
    try:
        os.makedirs(dir, 0755)
    except OSError, (errno, msg):
        try:
            if errno == EEXIST and stat.S_ISDIR(os.stat(dir).st_mode):
                return
        except:
            pass

        log.error("could not create directory %s: %s" % (dir, msg))

## Get the total amount of swap memory.
# @return The total amount of swap memory in kilobytes, or 0 if unknown.
def swapAmount():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("SwapTotal:"):
            fields = string.split(l)
            return int(fields[1])
    return 0

## Copy a device node.
# Copies a device node by looking at the device type, major and minor device
# numbers, and doing a mknod on the new device name.
#
# @param src The name of the source device node.
# @param dest The name of the new device node to create.
def copyDeviceNode(src, dest):
    filestat = os.lstat(src)
    mode = filestat[stat.ST_MODE]
    if stat.S_ISBLK(mode):
        type = stat.S_IFBLK
    elif stat.S_ISCHR(mode):
        type = stat.S_IFCHR
    else:
        # XXX should we just fallback to copying normally?
        raise RuntimeError, "Tried to copy %s which isn't a device node" % (src,)

    os.mknod(dest, mode | type, filestat.st_rdev)

## Create the device mapper control node.
# @param root The root of the filesystem to create the device node in.
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
    try:
        os.mknod(root + "/dev/mapper/control", stat.S_IFCHR | 0600,
               os.makedev(major, minor))
    except:
        pass

## Make some miscellaneous character device nodes.
def makeCharDeviceNodes():
    for dev in ["input/event0", "input/event1", "input/event2", "input/event3"]:
        isys.makeDevInode(dev, "/dev/%s" % (dev,))

## Make the device nodes for all the drives in the system.
def makeDriveDeviceNodes():
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
            num = 16

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

    tapeDrives = isys.tapeDriveList()
    for drive in tapeDrives:
        # make all tape device variants (stX,stXl,stXm,stXa,nstX,nstXl,nstXm,nstXa)
        for prefix in ("", "n"):
            for postfix in ("", "l", "m", "a"):
                device = "%s%s%s" % (prefix, drive, postfix)
                isys.makeDevInode(device, "/dev/%s" % (device,))

    for mdMinor in range(0, 32):
        md = "md%d" %(mdMinor,)
        isys.makeDevInode(md, "/dev/%s" %(md,))

    # make the node for the device mapper
    makeDMNode()

    # make loop devices
    for loopMinor in range(0, 8):
        loop = "loop%d" %(loopMinor,)
        isys.makeDevInode(loop, "/dev/%s" %(loop,))

## Determine if the hardware supports iSeries storage devices.
# @return 1 if so, 0 otherwise.
def hasiSeriesNativeStorage():
    # this is disgusting and I feel very dirty
    if rhpl.getArch() != "ppc":
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

## Get the PPC machine variety type.
# @return The PPC machine type, or 0 if not PPC.
def getPPCMachine():
    if rhpl.getArch() != "ppc":
        return 0

    machine = rhpl.getPPCMachine()
    if machine is None:
        log.warning("Unable to find PowerPC machine type")
    elif machine == 0:
        log.warning("Unknown PowerPC machine type: %s" %(machine,))

    return machine

## Get the powermac machine ID.
# @return The powermac machine id, or 0 if not PPC.
def getPPCMacID():
    machine = None

    if rhpl.getArch() != "ppc":
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

## Get the powermac generation.
# @return The powermac generation, or 0 if not powermac.
def getPPCMacGen():
    # XXX: should NuBus be here?
    pmacGen = ['OldWorld', 'NewWorld', 'NuBus']

    if rhpl.getArch() != "ppc":
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

## Determine if the hardware is an iBook or PowerBook
# @return 1 if so, 0 otherwise.
def getPPCMacBook():
    if rhpl.getArch() != "ppc":
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

cell = None
## Determine if the hardware is the Cell platform.
# @return True if so, False otherwise.
def isCell():
    global cell
    if cell is not None:
        return cell

    cell = False
    if rhpl.getArch() != "ppc":
        return cell

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if not string.find(line, 'Cell') == -1:
          cell = True

    return cell

mactel = None
## Determine if the hardware is an Intel-based Apple Mac.
# @return True if so, False otherwise.
def isMactel():
    global mactel
    if mactel is not None:
        return mactel

    if rhpl.getArch() not in ("x86_64", "i386"):
        mactel = False
    elif not os.path.exists("/usr/sbin/dmidecode"):
        mactel = False
    else:
        buf = execWithCapture("/usr/sbin/dmidecode",
                              ["dmidecode", "-s", "system-manufacturer"])
        if buf.lower().find("apple") != -1:
            mactel = True
        else:
            mactel = False
    return mactel

efi = None
## Determine if the hardware supports EFI.
# @return True if so, False otherwise.
def isEfi():
    global efi
    if efi is not None:
        return efi

    # XXX need to make sure efivars is loaded...
    if not os.path.exists("/sys/firmware/efi"):
        efi = False
    else:
        efi = True

    return efi

## Extract the CPU feature flags from /proc/cpuinfo
# @return A list of CPU feature flags, or an empty list on error.
def cpuFeatureFlags():
    if rhpl.getArch() not in ("i386", "x86_64"):
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
        return flst

    return []

## Generate the /etc/rpm/platform and /etc/rpm/macros files.
# @param root The root of the filesystem to create the files in.
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
    if flags.targetarch != None:
        myarch = flags.targetarch

    # now make the current install believe it, too
    rhpl.arch.canonArch = myarch

    f = open("%s/etc/rpm/platform" %(root,), 'w+')
    f.write("%s-redhat-linux\n" %(myarch,))
    f.close()

    # FIXME: writing /etc/rpm/macros feels wrong somehow
    # temporary workaround for #92285
    if not (myarch.startswith("ppc64") or
            myarch in ("s390x", "sparc64", "x86_64", "ia64")):
        return
    if os.access("%s/etc/rpm/macros" %(root,), os.R_OK):
        if myarch.startswith("ppc64") or myarch == "sparc64":
            f = open("%s/etc/rpm/macros" %(root,), 'r+')
            lines = f.readlines()
            addPrefer = True
            for line in lines:
                if line.startswith("%_prefer_color"):
                    addPrefer = False
            if addPrefer:    
                f.write("%_prefer_color   1\n")
            f.close()
            return
        else:
            return

    f = open("%s/etc/rpm/macros" %(root,), 'w+')
    f.write("%_transaction_color   3\n")
    if myarch.startswith("ppc64") or myarch == "sparc64":
        f.write("%_prefer_color   1\n")

    f.close()
