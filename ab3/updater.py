#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import time
import json
import manpa
import shutil
import random
import socket
import subprocess
import xml.dom.minidom
from datetime import datetime
from datetime import timedelta


class Main:

    def __init__(self, sock):
        args = json.loads(sys.argv[1])

        self.sock = sock
        self.dataDir = args["data-directory"]
        self.logDir = args["log-directory"]
        self.isDebug = (args["debug-flag"] != "")
        self.mp = manpa.Manpa(isDebug=self.isDebug)
        self.p = InfoPrinter()

    def run(self):
        # get latest local data
        lastDate = None
        if True:
            dlist = sorted(os.listdir(self.dataDir), reversed=True)
            for fn in dlist:
                if os.path.isdir(fn) and re.match("[0-9]+-[0-9]+-[0-9]+", fn):
                    lastDate = datetime.strptime(fn, "%Y-%m-%d")

        # get remote data
        self.p.print("Processing remote data")
        self.p.incIndent()
        try:
            linkList = []
            with self.mp.open_selenium_client() as driver:
                # open main page
                driver.get_and_wait("http://ab3.com.cn/xwlb.html")

                # get links
                for liTag in driver.find_elements_by_xpath("/html/body/div[7]/div/div[1]/div[2]/ul/li"):
                    try:
                        liTag.mark_elements_identified()
                        spanTag = liTag.find_elements_by_xpath("./span")
                        if datetime.strptime(spanTag.text, "%Y-%m-%d") >= lastDate + timedelta(days=1):
                            spanTag.mark_identified()
                            aTag = liTag.find_elements_by_xpath("./a")
                            aTag.mark_identified()
                            linkList.append((spanTag.text, aTag))
                            break
                    except ValueError:
                        spanTag.mark_error()

                # open detail page, save data
                for timeStr, aTag in linkList:
                    tdir = os.path.join(self.dataDir, timeStr)
                    Util.ensureDir(tdir)

                    driver.get_and_wait(aTag.href)
                    div = driver.find_elements_by_xpath("//div[@class='content-txt']")
                    content = xml.dom.minidom.parseString(div.innerHtml)

                    # FIXME: save video

                    # save text data
                    with open(os.path.join(tdir, "content.html"), "w") as f:
                        f.write("<html>\n")
                        f.write("  <body>\n")
                        f.write("    %s\n" % (content.toxml()))
                        f.write("  </body>\n")
                        f.write("</html>\n")
        finally:
            self.p.decIndent()


class MUtil:

    @staticmethod
    def connect():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/run/mirrors/api.socket")
        return sock

    @staticmethod
    def progress_changed(sock, progress):
        sock.send(json.dumps({
            "message": "progress",
            "data": {
                "progress": progress,
            },
        }).encode("utf-8"))
        sock.send(b'\n')

    @staticmethod
    def error_occured(sock, exc_info):
        sock.send(json.dumps({
            "message": "error",
            "data": {
                "exc_info": "abc",
            },
        }).encode("utf-8"))
        sock.send(b'\n')


class Util:

    @staticmethod
    def forceDelete(filename):
        if os.path.islink(filename):
            os.remove(filename)
        elif os.path.isfile(filename):
            os.remove(filename)
        elif os.path.isdir(filename):
            shutil.rmtree(filename)

    @staticmethod
    def randomSorted(tlist):
        return sorted(tlist, key=lambda x: random.random())

    @staticmethod
    def wgetCommonDownloadParam():
        return "-t 0 -w 60 --random-wait -T 60 --passive-ftp"

    @staticmethod
    def ensureDir(dirname):
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    @staticmethod
    def shellExec(cmd):
        ret = subprocess.run(cmd, shell=True, universal_newlines=True)
        if ret.returncode > 128:
            time.sleep(1.0)
        ret.check_returncode()

    @staticmethod
    def shellCall(cmd):
        # call command with shell to execute backstage job
        # scenarios are the same as Util.cmdCall

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            ret.check_returncode()
        return ret.stdout.rstrip()


class InfoPrinter:

    def __init__(self):
        self.indent = 0

    def incIndent(self):
        self.indent = self.indent + 1

    def decIndent(self):
        assert self.indent > 0
        self.indent = self.indent - 1

    def print(self, s):
        line = ""
        line += "\t" * self.indent
        line += s
        print(line)


###############################################################################

if __name__ == "__main__":
    sock = MUtil.connect()
    try:
        Main(sock).run()
        MUtil.progress_changed(sock, 100)
    except Exception:
        MUtil.error_occured(sock, sys.exc_info())
        raise
    finally:
        sock.close()
