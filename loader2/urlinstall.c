/*
 * urlinstall.c - code to set up url (ftp/http) installs
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
 * All rights reserved.
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

#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>

#include "../isys/iface.h"

#include "copy.h"
#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "log.h"
#include "method.h"
#include "net.h"
#include "method.h"
#include "urlinstall.h"
#include "cdinstall.h"
#include "urls.h"
#include "windows.h"

/* boot flags */
extern uint64_t flags;

static int loadSingleUrlImage(struct iurlinfo * ui, char *path,
                              char * dest, char * mntpoint, char * device,
                              int silentErrors) {
    int fd;
    int rc = 0;
    char *ehdrs = NULL;

    if (ui->protocol == URL_METHOD_HTTP) {
        char *arch = getProductArch();
        char *name = getProductName();
        int q;

        q = asprintf(&ehdrs, "User-Agent: anaconda/%s\r\n"
                             "X-Anaconda-Architecture: %s\r\n"
                             "X-Anaconda-System-Release: %s\r\n",
                     VERSION, arch, name);
    }

    fd = urlinstStartTransfer(ui, path, ehdrs);

    if (fd == -2) {
        if (ehdrs) free (ehdrs);
        return 2;
    }
    else if (fd < 0) {
        if (!silentErrors) {
            newtWinMessage(_("Error"), _("OK"),
                           _("Unable to retrieve %s://%s/%s."),
                           (ui->protocol == URL_METHOD_FTP ? "ftp" : "http"),
                           ui->address, path);
        }

        if (ehdrs) free (ehdrs);
        return 2;
    }

    if (dest != NULL) {
        rc = copyFileAndLoopbackMount(fd, dest, device, mntpoint);
    }

    urlinstFinishTransfer(ui, fd);
    return rc;
}

static void copyWarnFn (char *msg) {
   logMessage(WARNING, msg);
}

static void copyErrorFn (char *msg) {
   newtWinMessage(_("Error"), _("OK"), _(msg));
}

static int loadUrlImages(struct iurlinfo * ui) {
    char *stage2img, *buf, *path, *tmp;
    int rc;

    /* We assume that if stage2= was given, it's pointing at a stage2 image
     * file.  Trim the filename off the end, and that's the directory where
     * updates.img and friends must live.
     */
    if (FL_STAGE2(flags)) {
        /* Has to have a / in it somewhere, since it has to be a path name. */
        if (!strrchr(ui->prefix, '/'))
            return 1;
        else
            path = strndup(ui->prefix, strrchr(ui->prefix, '/') - ui->prefix);

        if (!path)
            return 1;
    }
    else
        rc = asprintf(&path, "%s/images", ui->prefix);

    /* grab the updates.img before netstg1.img so that we minimize our
     * ramdisk usage */
    rc = asprintf(&buf, "%s/%s", path, "updates.img");
    if (!loadSingleUrlImage(ui, buf,
                            "/tmp/updates-disk.img", "/tmp/update-disk",
                            "/dev/loop7", 1)) {
        copyDirectory("/tmp/update-disk", "/tmp/updates", copyWarnFn,
                      copyErrorFn);
        umountLoopback("/tmp/update-disk", "/dev/loop7");
        unlink("/tmp/updates-disk.img");
        unlink("/tmp/update-disk");
    }

    free(buf);

    /* grab the product.img before netstg1.img so that we minimize our
     * ramdisk usage */
    rc = asprintf(&buf, "%s/%s", path, "product.img");
    if (!loadSingleUrlImage(ui, buf,
                            "/tmp/product-disk.img", "/tmp/product-disk",
                            "/dev/loop7", 1)) {
        copyDirectory("/tmp/product-disk", "/tmp/product", copyWarnFn,
                      copyErrorFn);
        umountLoopback("/tmp/product-disk", "/dev/loop7");
        unlink("/tmp/product-disk.img");
        unlink("/tmp/product-disk");
    }

    free(buf);

    if (!FL_STAGE2(flags)) {
        /* require 128MB for use of graphical stage 2 due to size of image */
        if (totalMemory() < GUI_STAGE2_RAM) {
            stage2img = "minstg2.img";
            logMessage(WARNING, "URLINSTALL falling back to non-GUI stage2 "
                           "due to insufficient RAM");
        } else {
            stage2img = "stage2.img";
        }

        rc = asprintf(&buf, "%s/%s", path, stage2img);
        rc = asprintf(&tmp, "/tmp/%s", stage2img);
        rc = loadSingleUrlImage(ui, buf, tmp,
                                "/mnt/runtime", "/dev/loop0", 0);
        free(buf);
    }
    else {
        /* We already covered the case of ui->prefix not having a / in it
         * at the beginning, so don't worry about it here.
         */
        rc = asprintf(&tmp, "/tmp/%s", strrchr(ui->prefix, '/'));
        rc = loadSingleUrlImage(ui, ui->prefix, tmp, "/mnt/runtime",
                                "/dev/loop0", 0);
    }

    free(tmp);
    free(path);

    if (rc) {
        if (rc != 2) 
            newtWinMessage(_("Error"), _("OK"),
                           _("Unable to retrieve the install image."));
        return 1;
    }

    /* now verify the stamp... */
    if (!verifyStamp("/mnt/runtime")) {
        rc = asprintf(&buf, _("The %s installation tree in that directory does "
                              "not seem to match your boot media."), 
                 getProductName());

	newtWinMessage(_("Error"), _("OK"), buf);

	umountLoopback("/mnt/runtime", "/dev/loop0");
	return 1;
    }

    return 0;
}

char * mountUrlImage(struct installMethod * method,
                     char * location, struct loaderData_s * loaderData) {
    int rc;
    char *url, *buf;
    struct iurlinfo ui;
    char needsSecondary = ' ';
    int dir = 1;
    char * cdurl = NULL;

    enum { URL_STAGE_MAIN, URL_STAGE_SECOND, URL_STAGE_FETCH, 
           URL_STAGE_DONE } stage = URL_STAGE_MAIN;

    memset(&ui, 0, sizeof(ui));

    while (stage != URL_STAGE_DONE) {
        switch(stage) {
        case URL_STAGE_MAIN:
            if (loaderData->method == METHOD_URL && loaderData->methodData) {
                url = ((struct urlInstallData *)loaderData->methodData)->url;
                logMessage(INFO, "URL_STAGE_MAIN - url is %s", url);

                if (!url) {
                    logMessage(ERROR, "missing url specification");
                    flags &= ~LOADER_FLAGS_STAGE2;
                    loaderData->method = -1;
                    break;
                }

		/* explode url into ui struct */
		convertURLToUI(url, &ui);

		/* ks info was adequate, lets skip to fetching image */
		stage = URL_STAGE_FETCH;
		dir = 1;
		break;
            } else {
                flags &= ~LOADER_FLAGS_STAGE2;

	        if (urlMainSetupPanel(&ui, &needsSecondary))
                    return NULL;
            }

	    /* got required information from user, proceed */
	    stage = (needsSecondary != ' ') ? URL_STAGE_SECOND : 
		URL_STAGE_FETCH;
	    dir = 1;
            break;

        case URL_STAGE_SECOND:
            rc = urlSecondarySetupPanel(&ui);
            if (rc) {
                stage = URL_STAGE_MAIN;
                dir = -1;
            } else {
                stage = URL_STAGE_FETCH;
                dir = 1;
            }
            break;

        case URL_STAGE_FETCH:
            if (FL_TESTING(flags)) {
                stage = URL_STAGE_DONE;
                dir = 1;
                break;
            }

            /* See if we have a stage2 on a local CD before trying to pull
             * one over the network.  However, passing stage2= overrides
             * this check.
             */
            if (!FL_STAGE2(flags))
                cdurl = findAnacondaCD(location, 0);

	    if (cdurl) {
		/* verify that our URL is specifying the correct tree */
		/* we do this by attempting to pull a .discinfo file */
                rc = asprintf(&buf, "%s/%s/.discinfo", ui.address, ui.prefix);
		if (loadSingleUrlImage(&ui, buf, NULL, NULL, NULL, 1)) {
                        free(buf);
                        umountStage2();
                        umount(location);
                        unlink("/tmp/cdrom");

			stage = URL_STAGE_MAIN;
			dir = -1;

			if (loaderData->method >= 0)
				loaderData->method = -1;

			break;
		}

		logMessage(INFO, "Detected stage 2 image on CD");
		winStatus(50, 3, _("Media Detected"), 
			  _("Local installation media detected..."), 0);
		sleep(3);
		newtPopWindow();
                free(buf);

                stage = URL_STAGE_DONE;
                dir = 1;
            } else {
		/* need to find stage 2 on remote site */
		if (loadUrlImages(&ui)) {
		    stage = URL_STAGE_MAIN;
		    dir = -1;
		    if (loaderData->method >= 0) {
			loaderData->method = -1;
		    }

                    flags &= ~LOADER_FLAGS_STAGE2;
		} else {
		    stage = URL_STAGE_DONE;
		    dir = 1;
		}
	    }
            break;

        case URL_STAGE_DONE:
            break;
        }
    }

    url = convertUIToURL(&ui);
    return url;
}

int getFileFromUrl(char * url, char * dest, 
                   struct loaderData_s * loaderData) {
    int retval = 0;
    struct iurlinfo ui;
    enum urlprotocol_t proto = 
        !strncmp(url, "ftp://", 6) ? URL_METHOD_FTP : URL_METHOD_HTTP;
    char * host = NULL, * file = NULL, * chptr = NULL, *login = NULL, *password = NULL;
    int fd, rc;
    struct networkDeviceConfig netCfg;
    char *ehdrs = NULL, *ip = NULL;

    if (kickstartNetworkUp(loaderData, &netCfg)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    memset(&ui, 0, sizeof(ui));
    ui.protocol = proto;

    if ((ip = iface_ip2str(loaderData->netDev)) == NULL) {
        logMessage(ERROR, "getFileFromUrl: no client IP information");
        return 1;
    }

    getHostPathandLogin((proto == URL_METHOD_FTP ? url + 6 : url + 7),
                   &host, &file, &login, &password, ip);

    logMessage(INFO, "file location: %s://%s%s", 
               (proto == URL_METHOD_FTP ? "ftp" : "http"), host, file);

    chptr = strchr(host, '/');
    if (chptr == NULL) {
        ui.address = strdup(host);
        ui.prefix = strdup("/");
    } else {
        *chptr = '\0';
        ui.address = strdup(host);
        host = chptr;
        *host = '/';
        ui.prefix = strdup(host);
    }

    if (password[0] != '\0')
        ui.password = strdup (password);
    if (login[0] != '\0')
        ui.login = strdup (login);

    if (proto == URL_METHOD_HTTP) {
        char *arch = getProductArch();
        char *name = getProductName();
        int q;

        q = asprintf(&ehdrs, "User-Agent: anaconda/%s\r\n"
                             "X-Anaconda-Architecture: %s\r\n"
                             "X-Anaconda-System-Release: %s\r\n",
                     VERSION, arch, name);
    }

    if (proto == URL_METHOD_HTTP && FL_KICKSTART_SEND_MAC(flags)) {
        /* find all ethernet devices and make a header entry for each one */
        int i, q;
        char *dev, *mac, *tmpstr;
        struct device **devices;

        devices = getDevices(DEVICE_NETWORK);
        for (i = 0; devices && devices[i]; i++) {
            dev = devices[i]->device;
            mac = iface_mac2str(dev);

            if (mac) {
                q = asprintf(&tmpstr, "X-RHN-Provisioning-MAC-%d: %s %s\r\n",
                             i, dev, mac);

                if (!ehdrs) {
                    ehdrs = strdup(tmpstr);
                } else {
                    ehdrs = (char *) realloc(ehdrs, strlen(ehdrs)+strlen(tmpstr)+1);
                    strcat(ehdrs, tmpstr);
                }

                free(mac);
                free(tmpstr);
            }
        }
    }

    fd = urlinstStartTransfer(&ui, file, ehdrs);
    if (fd < 0) {
        logMessage(ERROR, "failed to retrieve http://%s/%s%s", ui.address, ui.prefix, file);
        retval = 1;
        goto err;
    }

    rc = copyFileFd(fd, dest);
    if (rc) {
        unlink (dest);
        logMessage(ERROR, "failed to copy file to %s", dest);
        retval = 1;
        goto err;
    }

    urlinstFinishTransfer(&ui, fd);

err:
    if (file) free(file);
    if (ehdrs) free(ehdrs);
    if (host) free(host);
    if (login) free(login);
    if (password) free(password);

    return retval;
}

/* pull kickstart configuration file via http */
int kickstartFromUrl(char * url, struct loaderData_s * loaderData) {
    return getFileFromUrl(url, "/tmp/ks.cfg", loaderData);
}

void setKickstartUrl(struct loaderData_s * loaderData, int argc,
		    char ** argv) {

    char *url = NULL;
    poptContext optCon;
    int rc;
    struct poptOption ksUrlOptions[] = {
        { "url", '\0', POPT_ARG_STRING, &url, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    logMessage(INFO, "kickstartFromUrl");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksUrlOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to Url kickstart method "
                         "command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    if (!url) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Must supply a --url argument to Url kickstart method."));
        return;
    }

    /* determine install type */
    if (strstr(url, "http://") || strstr(url, "ftp://"))
	loaderData->method = METHOD_URL;
    else {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown Url method %s"), url);
        return;
    }

    loaderData->methodData = calloc(sizeof(struct urlInstallData *), 1);
    ((struct urlInstallData *)loaderData->methodData)->url = url;

    logMessage(INFO, "results of url ks, url %s", url);
}

/* vim:set shiftwidth=4 softtabstop=4: */
