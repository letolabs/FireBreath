#!/usr/bin/env python
# encoding: utf-8
"""
Utility script to import doxygen docs into confluence

Original Author(s): Richard Bateman
Created:    18 October 2009
License:    Dual license model; choose one of two:
            New BSD License
            http://www.opensource.org/licenses/bsd-license.php
            - or -
            GNU Lesser General Public License, version 2.1
            http://www.gnu.org/licenses/lgpl-2.1.html

Copyright 2009 the Firebreath development team
"""
import os, sys, xmlrpclib
from xml.dom import minidom
from itertools import izip

nameCount = {}

class Doxygen2Confluence:
    nameCount = {}
    inputHtmlPath = os.path.join("docs", "html")
    outputHtmlPath = os.path.join("docs", "patched")
    inputList = {}
    pathMap = {}
    baseUrl = "/display/ClassDocs/%s"
    classDocsUrl = "http://classdocs.firebreath.org/"
    server = xmlrpclib.ServerProxy("http://firebreath.org/rpc/xmlrpc")
    rpc = server.confluence1
    token = ""
    space = "ClassDocs"
    topPages = {
            "class" : "1279494",
            "struct" : "1279496",
            "namespace" : "1278039",
            "file" : "1279498",
            }
    parents = {}
    createdPages = []

    def __init__(self, username, password):
        self.token = self.rpc.login(username, password)

    def getName(self, name):
        count = 1
        retVal = name.replace("::", " ")
        if name in self.nameCount:
            count = self.nameCount[name]
            count = count + 1
            retVal = "%s (%s)" % (name, count)

        self.nameCount[name] = count
        return retVal.replace("<", "(").replace(">", ")").replace("/", " ")


    def exportToConfluence(self, refId, pageName, kind):
        try:
            page = self.rpc.getPage(self.token, self.space, pageName)
        except:
            page = {"space": self.space, "title": pageName}

        page["parentId"] = self.parents[refId]
        if kind == "file":
            filename = "%s_source.html" % refId
        else:
            filename = "%s.html" % refId
        page["content"] = "{doxygen_init}{doxygen_init}{html-include:url=http://classdocs.firebreath.org/patched/%s}" % filename

        while True:
            try:
                page = self.rpc.storePage(self.token, page)
                self.createdPages.append(page["id"])
                pass
            except:
                pass
            break

        return page["id"]

    def cleanConfluence(self):
        for kind, id in self.topPages.items():
            print "Scanning pages for %s (id %s)" % (kind, id)
            pages = self.rpc.getDescendents(self.token, id)
            for page in pages:
                if (page["id"] not in self.createdPages) and (page["id"] not in self.topPages.values()):
                    print "Removing defunct page: %s (%s)" % (page["title"], page["id"])
                    self.rpc.removePage(self.token, page["id"])

    def processDirectory(self, path):
        xml = minidom.parse("docs/xml/index.xml")

        compounds = xml.documentElement.getElementsByTagName("compound")
        refidMap = {}
        Info = {}
        for com in compounds:
            refid = com.getAttribute("refid")
            kind = com.getAttribute("kind")
            compoundName = com.getElementsByTagName("name")[0].firstChild.wholeText
            realName = self.getName("%s %s" % (kind, compoundName.replace("::", " ")))
            if os.path.exists(os.path.join(path, "%s-members.html" % refid)):
                refidMap["%s-members.html" % refid] = self.baseUrl % (realName + " Members")
            filename = "%s.html" % refid
            if kind == "file":
                filename = "%s_source.html" % refid
            if os.path.exists(os.path.join(path, filename)):
                Info[refid] = {}
                Info[refid]["kind"] = kind
                Info[refid]["name"] = realName
                Info[refid]["members"] = {}
                refidMap[filename] = self.baseUrl % realName
                if kind == "file":
                    print "%s => %s" % (filename, self.baseUrl % realName)
                    continue
                for mem in com.getElementsByTagName("member"):
                    memName = mem.getElementsByTagName("name")[0].firstChild.wholeText
                    memRefId = mem.getAttribute("refid")
                    memRefId = memRefId[0:memRefId.rindex("_")]
                    memKind = mem.getAttribute("kind")

                    if (os.path.exists(os.path.join(path, memRefId + ".html"))):
                        localName = self.getName(Info[refid]["name"] + " " + memName)
                        refidMap["%s.html" % memRefId] = self.baseUrl % localName
                        Info[refid]["members"][memRefId] = {}
                        Info[refid]["members"][memRefId]["kind"] = memKind
                        Info[refid]["members"][memRefId]["name"] = localName
        self.inputList = Info
        self.pathMap = refidMap

    def processFile(self, filename, inPath, outPath):
        f = open(os.path.join(inPath, filename), "r")
        fileText = f.read()
        f.close()

        for id, url in izip(self.pathMap.keys(), self.pathMap.values()):
            #print "Changing %s to %s" % (id, url)
            fileText = fileText.replace(id, url)
        fileText = fileText.replace(r'img src="', r'img src="http://classdocs.firebreath.org/')

        nf = open(os.path.join(outPath, filename), "w")
        nf.write(fileText)
        nf.close()

    def writeNewFiles(self, inPath, outPath):
        if not os.path.exists(outPath):
            os.mkdir(outPath)

        # Now we're going to load the files, process them, and write them to the output directory
        for refid, item in self.inputList.items():
            filename = "%s.html" % refid
            if item["kind"] == "file":
                filename = "%s_source.html" % refid
            #print "Opening file %s" % filename
            self.processFile(filename, inPath, outPath)
            for memid, mem in item["members"].items():
                #print "Member: %s" % memid
                self.processFile("%s.html" % memid, inPath, outPath)


    def begin(self):
        self.processDirectory(self.inputHtmlPath)
        self.writeNewFiles(self.inputHtmlPath, self.outputHtmlPath)

        for refid, item in self.inputList.items():
            parentId = None
            if item["kind"] in self.topPages:
                parentId = self.topPages[item["kind"]]
            else:
                print "Could not find %s in " % item["kind"], self.topPages
                continue
            self.parents[refid] = parentId
            print "Exporting %s to confluence..." % item["name"]
            pageId = self.exportToConfluence(refid, item["name"], item["kind"])
            for memid, mem in item["members"].items():
                #print "Exporting %s to confluence..." % mem["name"]
                self.parents[memid] = pageId
                self.exportToConfluence(memid, mem["name"], mem["kind"])
        self.cleanConfluence()


def Main():
    """
    Parse the commandline and execute the appropriate actions.
    """
    a = Doxygen2Confluence(sys.argv[1], sys.argv[2])
    a.begin()

if __name__ == "__main__":
    Main()

