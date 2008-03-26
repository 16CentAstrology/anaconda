/*
 * nfsinstall.c - code to set up nfs installs
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005,
 * 2006, 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "loader.h"
#include "lang.h"
#include "loadermisc.h"
#include "kickstart.h"
#include "log.h"
#include "method.h"
#include "nfsinstall.h"
#include "net.h"
#include "cdinstall.h"
#include "windows.h"

#include "../isys/imount.h"
#include "../isys/iface.h"

/* boot flags */
extern uint64_t flags;

int nfsGetSetup(char ** hostptr, char ** dirptr) {
    struct newtWinEntry entries[3];
    char * buf;
    char * newServer = *hostptr ? strdup(*hostptr) : NULL;
    char * newDir = *dirptr ? strdup(*dirptr) : NULL;
    int rc;

    entries[0].text = _("NFS server name:");
    entries[0].value = &newServer;
    entries[0].flags = NEWT_FLAG_SCROLL;
    rc = asprintf(&entries[1].text, _("%s directory:"), getProductName());
    entries[1].value = &newDir;
    entries[1].flags = NEWT_FLAG_SCROLL;
    entries[2].text = NULL;
    entries[2].value = NULL;
    rc = asprintf(&buf, _("Please enter the server name and path to your %s "
                          "images."), getProductName());
    rc = newtWinEntries(_("NFS Setup"), buf, 60, 5, 15,
                        24, entries, _("OK"), _("Back"), NULL);
    free(buf);
    free(entries[1].text);

    if (rc == 2) {
        if (newServer) free(newServer);
        if (newDir) free(newDir);
        return LOADER_BACK;
    }

    if (*hostptr) free(*hostptr);
    if (*dirptr) free(*dirptr);
    *hostptr = newServer;
    *dirptr = newDir;

    return 0;
}

/* Check if we are using an nfsiso installation method.  Assumptions:  nothing
 * is mounted before this function is called, /mnt/isodir is mounted at the
 * end if we are doing nfsiso.
 */
static char *isNfsIso(char *fullPath, char *mountOpts, int *foundinvalid,
                      int checkStage2) {
    char *path = NULL;

    if (!doPwMount(fullPath, "/mnt/isodir", "nfs", mountOpts)) {
        if ((path = validIsoImages("/mnt/isodir", foundinvalid, checkStage2)) == NULL)
            umount("/mnt/isodir");
    }

    return path;
}

char * mountNfsImage(struct installMethod * method,
                     char * location, struct loaderData_s * loaderData) {
    char * host = NULL;
    char * directory = NULL;
    char * mountOpts = NULL;
    char * fullPath = NULL;
    char * url = NULL;

    enum { NFS_STAGE_NFS, NFS_STAGE_MOUNT, 
           NFS_STAGE_DONE } stage = NFS_STAGE_NFS;

    int rc, tmp, foundinvalid = 0;

    /* JKFIXME: ASSERT -- we have a network device setup when we get here */
    while (stage != NFS_STAGE_DONE) {
        switch (stage) {
        case NFS_STAGE_NFS:
            logMessage(INFO, "going to do nfsGetSetup");
            if (loaderData->method == METHOD_NFS && loaderData->methodData) {
                host = ((struct nfsInstallData *)loaderData->methodData)->host;
                directory = ((struct nfsInstallData *)loaderData->methodData)->directory;

                if (((struct nfsInstallData *) loaderData->methodData)->mountOpts == NULL)
                    mountOpts = strdup("ro");
                else
                    rc = asprintf(&mountOpts, "ro,%s", ((struct nfsInstallData *) loaderData->methodData)->mountOpts);

                logMessage(INFO, "host is %s, dir is %s, opts are '%s'", host, directory, mountOpts);

                if (!host || !directory) {
                    logMessage(ERROR, "missing host or directory specification");
                    flags &= ~LOADER_FLAGS_STAGE2;
                    loaderData->method = -1;
                    break;
                } else {
                    host = strdup(host);
                    directory = strdup(directory);
                }
            } else if (nfsGetSetup(&host, &directory) == LOADER_BACK) {
                flags &= ~LOADER_FLAGS_STAGE2;
                return NULL;
            }

            stage = NFS_STAGE_MOUNT;
            break;

        case NFS_STAGE_MOUNT: {
            char *buf, *stage2dir;
            struct in_addr ip;

            if (loaderData->noDns && !(inet_pton(AF_INET, host, &ip))) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Hostname specified with no DNS configured"));
                if (loaderData->method >= 0) {
                    loaderData->method = -1;
                }

                flags &= ~LOADER_FLAGS_STAGE2;
                break;
            }

            /* Try to see if we're booted off of a CD with stage2.  However,
             * passing stage2= overrides this check.
             */
            if (!FL_STAGE2(flags) && findAnacondaCD("/mnt/stage2", 0)) {
                logMessage(INFO, "Detected stage 2 image on CD");
                winStatus(50, 3, _("Media Detected"),
                          _("Local installation media detected..."), 0);
                sleep(3);
                newtPopWindow();

                stage = NFS_STAGE_DONE;
                tmp = asprintf(&fullPath, "%s:%s", host, directory);

                if ((buf = isNfsIso(fullPath, mountOpts, &foundinvalid, 0)) != NULL)
                    rc = asprintf(&url, "nfsiso:%s:%s", host, directory);
                else
                    rc = asprintf(&url, "nfs:%s:%s", host, directory);

                free(buf);
                break;
            }

            if (FL_STAGE2(flags)) {
                if (!strrchr(directory, '/')) {
                    flags &= ~LOADER_FLAGS_STAGE2;
                    return NULL;
                } else {
                    tmp = asprintf(&fullPath, "%s:%.*s/", host,
                                   (int) (strrchr(directory, '/') - directory), directory);
                }
            }
            else
                tmp = asprintf(&fullPath, "%s:%s", host, directory);

            logMessage(INFO, "mounting nfs path %s", fullPath);

            if (FL_TESTING(flags)) {
                stage = NFS_STAGE_DONE;
                break;
            }

            stage = NFS_STAGE_NFS;

            if (!doPwMount(fullPath, "/mnt/source", "nfs", mountOpts)) {
                if (FL_STAGE2(flags)) {
                    stage2dir = strdup("/mnt/source");
                    tmp = asprintf(&buf, "/mnt/source/%s", strrchr(directory, '/'));
                } else {
                    stage2dir = strdup("/mnt/source/images");
                    buf = strdup("/mnt/source/images/stage2.img");
                }

                winStatus(70, 3, _("Retrieving"), "%s %s...", _("Retrieving"), buf);
                rc = copyFile(buf, "/tmp/stage2.img");
                newtPopWindow();

                free(stage2dir);

                if (!rc) {
                    logMessage(INFO, "can access %s", buf);
                    rc = mountStage2("/tmp/stage2.img", stage2dir);

                    free(buf);

                    if (rc && rc == -1) {
                        foundinvalid = 1;
                        logMessage(WARNING, "not the right one");
                        umount("/mnt/source");
                    } else {
                        stage = NFS_STAGE_DONE;
                        rc = asprintf(&url, "nfs:%s:%s", host, directory);
                        break;
                    }
                } else {
                    char *path;

                    logMessage(WARNING, "unable to access %s", buf);
                    free(buf);
                    umount("/mnt/source");

                    if ((path = isNfsIso(fullPath, mountOpts, &foundinvalid, 1)) != NULL) {
                        /* If we get here, it wasn't a regular NFS method but it may
                         * still be NFSISO.  Remount on the isodir mountpoint and try
                         * again.
                         */
                        logMessage(INFO, "Path to valid iso is %s", path);
                        copyUpdatesImg("/mnt/isodir/updates.img");

                        if (mountLoopback(path, "/mnt/source", "/dev/loop1")) {
                            logMessage(WARNING, "failed to mount iso %s loopback", path);
                            free(path);
                        } else {
                            if (FL_STAGE2(flags)) {
                                stage2dir = strdup("/mnt/source");
                                tmp = asprintf(&buf, "/mnt/source/%s", strrchr(directory, '/'));
                            } else {
                                stage2dir = strdup("/mnt/source/images");
                                buf = strdup("/mnt/source/images/stage2.img");
                            }

                            rc = copyFile(buf, "/tmp/stage2.img");
                            rc = mountStage2("/tmp/stage2.img", stage2dir);
                            umountLoopback("/mnt/source", "/dev/loop1");

                            free(buf);
                            free(stage2dir);
                            free(path);

                            if (rc && rc == -1) {
                                foundinvalid = 1;
                                umount("/mnt/isodir");
                            } else {
                                stage = NFS_STAGE_DONE;
                                rc = asprintf(&url, "nfsiso:%s:%s", host, directory);
                                break;
                            }
                        }
                    }
                }
            } else {
                newtWinMessage(_("Error"), _("OK"),
                               _("That directory could not be mounted from "
                                 "the server."));
                if (loaderData->method >= 0) {
                    loaderData->method = -1;
                }
                break;
            }

            if (foundinvalid)
                rc = asprintf(&buf, _("The %s installation tree in that "
                                 "directory does not seem to match "
                                 "your boot media."), getProductName());
            else
                rc = asprintf(&buf, _("That directory does not seem to "
                                 "contain a %s installation tree."),
                               getProductName());

            newtWinMessage(_("Error"), _("OK"), buf);
            free(buf);

            if (loaderData->method >= 0) {
                loaderData->method = -1;
            }

            flags &= ~LOADER_FLAGS_STAGE2;
            break;
        }

        case NFS_STAGE_DONE:
            break;
        }
    }

    free(host);
    free(directory);
    if (fullPath)
        free(fullPath);

    return url;
}


void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    char * host = NULL, * dir = NULL, * mountOpts = NULL;
    poptContext optCon;
    int rc;
    struct poptOption ksNfsOptions[] = {
        { "server", '\0', POPT_ARG_STRING, &host, 0, NULL, NULL },
        { "dir", '\0', POPT_ARG_STRING, &dir, 0, NULL, NULL },
        { "opts", '\0', POPT_ARG_STRING, &mountOpts, 0, NULL, NULL},
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    logMessage(INFO, "kickstartFromNfs");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksNfsOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to NFS kickstart method "
                         "command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    if (!host || !dir) {
        logMessage(ERROR, "host and directory for nfs kickstart not specified");
        return;
    }

    loaderData->method = METHOD_NFS;
    loaderData->methodData = calloc(sizeof(struct nfsInstallData *), 1);
    ((struct nfsInstallData *)loaderData->methodData)->host = host;
    ((struct nfsInstallData *)loaderData->methodData)->directory = dir;
    ((struct nfsInstallData *)loaderData->methodData)->mountOpts = mountOpts;

    logMessage(INFO, "results of nfs, host is %s, dir is %s, opts are '%s'",
               ((struct nfsInstallData *) loaderData->methodData)->host,
               ((struct nfsInstallData *) loaderData->methodData)->directory,
               ((struct nfsInstallData *) loaderData->methodData)->mountOpts);
}


int getFileFromNfs(char * url, char * dest, struct loaderData_s * loaderData) {
    char * host = NULL, *path = NULL, * file = NULL, * opts = NULL;
    char * chk = NULL, *ip = NULL;
    int failed = 0;
    int i;
    struct networkDeviceConfig netCfg;

    if (kickstartNetworkUp(loaderData, &netCfg)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    /* if they just did 'linux ks', they want us to figure it out from
     * the dhcp/bootp information
     */
    if (url == NULL) {
        char ret[47];
        ip_addr_t *tip;

        if (!(netCfg.dev.set & PUMP_INTFINFO_HAS_NEXTSERVER)) {
            logMessage(ERROR, "no bootserver was found");
            return 1;
        }

        tip = &(netCfg.dev.nextServer);
        if (!(netCfg.dev.set & PUMP_INTFINFO_HAS_BOOTFILE)) {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            i = asprintf(&url, "%s:%s", ret, "/kickstart/");
            logMessage(ERROR, "bootp: no bootfile received");
        } else {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            i = asprintf(&url, "%s:%s", ret, netCfg.dev.bootFile);
            logMessage(INFO, "bootp: bootfile is %s", netCfg.dev.bootFile);
        }
    }

    /* get the IP of the target system */
    if ((ip = iface_ip2str(loaderData->netDev)) == NULL) {
        logMessage(ERROR, "nl_ip2str returned NULL");
        return 1;
    }

    logMessage(INFO, "url is %s", url);
    getHostandPath(url, &host, &path, ip);

    opts = strchr(host, ':');
    if (opts && (strlen(opts) > 1)) {
        char * c = opts;
        opts = host;
        host = c + 1;
        *c = '\0';
    } else {
        opts = NULL;
    }

    /* nfs has to be a little bit different... split off the last part as
     * the file and then concatenate host + dir path */
    file = strrchr(path, '/');
    if (!file) {
        file = path;
    } else {
        *file++ ='\0';
        chk = host + strlen(host)-1;

        if (*chk == '/' || *path == '/')
            i = asprintf(&host, "%s%s", host, path);
        else
            i = asprintf(&host, "%s/%s", host, path);
    }

    logMessage(INFO, "file location: nfs:%s/%s", host, file);

    if (!doPwMount(host, "/tmp/mnt", "nfs", opts)) {
        char * buf;

        i = asprintf(&buf, "/tmp/mnt/%s", file);
        if (copyFile(buf, dest)) {
            logMessage(ERROR, "failed to copy file to %s", dest);
            failed = 1;
        }

        free(buf);
    } else {
        logMessage(ERROR, "failed to mount nfs source");
        failed = 1;
    }

    free(host);
    free(path);
    if (ip) free(ip);

    umount("/tmp/mnt");
    unlink("/tmp/mnt");

    return failed;
}

int kickstartFromNfs(char * url, struct loaderData_s * loaderData) {
    return getFileFromNfs(url, "/tmp/ks.cfg", loaderData);
}

/* vim:set shiftwidth=4 softtabstop=4: */
