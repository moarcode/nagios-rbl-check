#! /usr/bin/env python
#
# This is a multi-threaded RBL lookup check for Icinga / Nagios.
# Copyright (C) 2012 Frode Egeland <egeland[at]gmail.com>
#
# Modified by Kumina bv in 2013. We only added an option to use an
# address instead of a hostname.
#
# Modified by Guillaume Subiron (Sysnove) in 2015 : mainly PEP8
#
# Modified by Mateusz Pacek in 2015 : adjusted to check domains instead
# of IP addresses. List of servers loaded from config file in yaml.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
#

import sys
import os
import getopt
import socket

rv = (2, 6)
if rv >= sys.version_info:
    print "ERROR: Requires Python 2.6 or greater"
    sys.exit(3)

import Queue
import threading
import yaml

serverlist = []
default_file_c = "/etc/nagios3/scripts/rbl/rbl_domain_default.yml"
queue = Queue.Queue()
global on_blacklist
on_blacklist = []


class ThreadRBL(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            # grabs host from queue
            hostname, root_name = self.queue.get()
            check_host = "%s.%s" % (hostname, root_name)
            try:
                check_addr = socket.gethostbyname(check_host)
            except socket.error:
                check_addr = None
            if check_addr is not None and "127.0." in check_addr:
                on_blacklist.append(root_name)

            # signals to queue job is done
            self.queue.task_done()


def usage(argv0):
    print "%s -w <WARN level> -c <CRIT level> -h <hostname> [-f <config file>]" % argv0


def loadcfg(file_arg):
    with open(file_arg, 'r') as ymlfile:
        return yaml.load(ymlfile)


def main(argv, environ):
    options, remainder = getopt.getopt(argv[1:],
                                       "w:c:h:f:",
                                       ["warn=", "crit=", "host=", "config_file="])
    status = {'OK': 0, 'WARNING': 1, 'CRITICAL': 2, 'UNKNOWN': 3}
    host = None
    file_c = None

    if 4 > len(options) and file_c is not None:
        usage(argv[0])
        sys.exit(status['UNKNOWN'])
    elif 3 > len(options) and file_c is None:
        usage(argv[0])
        sys.exit(status['UNKNOWN'])

    for field, val in options:
        if field in ('-w', '--warn'):
            warn_limit = int(val)
        elif field in ('-c', '--crit'):
            crit_limit = int(val)
        elif field in ('-h', '--host'):
            host = val
        elif field in ('-f', '--file'):
            file_c = val
        else:
            usage(argv[0])
            sys.exit(status['UNKNOWN'])

# Config file load
    if file_c is not None:
        cfg = loadcfg(file_c)
    else:
        cfg = loadcfg(default_file_c)

# Append servers to list
    for srv in cfg.split():
        serverlist.append(srv)

# ##### Thread stuff:

    # spawn a pool of threads, and pass them queue instance
    for i in range(10):
        t = ThreadRBL(queue)
        t.setDaemon(True)
        t.start()

    # populate queue with data
    for blhost in serverlist:
        queue.put((host, blhost))

    # wait on the queue until everything has been processed
    queue.join()

# ##### End Thread stuff

    if on_blacklist:
        output = '%s on %s spam blacklists : %s' % (host,
                                                    len(on_blacklist),
                                                    ', '.join(on_blacklist))
        if len(on_blacklist) >= crit_limit:
            print 'CRITICAL: %s' % output
            sys.exit(status['CRITICAL'])
        if len(on_blacklist) >= warn_limit:
            print 'WARNING: %s' % output
            sys.exit(status['WARNING'])
        else:
            print 'OK: %s' % output
            sys.exit(status['OK'])
    else:
        print 'OK: %s not on known spam blacklists' % host
        sys.exit(status['OK'])


if __name__ == "__main__":
    main(sys.argv, os.environ)
