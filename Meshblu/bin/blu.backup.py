import sys, os, platform, re, inspect
import xml.dom.minidom, xml.sax.saxutils
import logging
import urllib2, urllib
import json
import sched, time
import csv

from MeshbluClass import *

import splunk.Intersplunk
import splunk.entity as entity

logging.root
logging.root.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.root.addHandler(handler)

(isgetinfo, sys.argv) = splunk.Intersplunk.isGetInfo(sys.argv)

if len(sys.argv) < 1:
    splunk.Intersplunk.parseError("No arguments provided")
    
if isgetinfo:
    splunk.Intersplunk.outputInfo(False, False, True, False, None, True)
    # outputInfo automatically calls sys.exit()    

def getCredentials():
	settings = dict()
	records = splunk.Intersplunk.readResults(settings = settings, has_header = True)
        myEnt = entity.getEntity('/meshbluep/config','config', namespace='Meshblu',sessionKey=settings['sessionKey'], owner='nobody')
        logging.debug(myEnt.get('meshblu_server'))
        return myEnt.get('meshblu_server'), myEnt.get('server_uuid'), myEnt.get('server_token')
    
def getParameters():
    argcount = len(sys.argv)
    params = re.findall('(\\w+)\s*=\s*"?(\\w+)', " ".join(sys.argv))
    p = {}
    for k,v in params:
        v = v.lower()
        p[k] = v
        logging.info("%s=%s"%(k,v))
    return p

try:
        p = getParameters()
        server, skynet_auth_uuid, skynet_auth_token = getCredentials()
        skynet = MeshbluAPI(server, skynet_auth_uuid, skynet_auth_token)
        requestUrl = "%s/"%server
        response = {}
        results = splunk.Intersplunk.readResults(None, None, False)
        if p['op'] == "status":
                 response = skynet.getStatus()
        elif p["op"] == "mydevices":
                 response = skynet.getMyDevices()
        elif p["op"] == "message":
                 response = skynet.sendMessage(p["devices"],p["payload"])
        elif p["op"] == "webhook":
                 p["uuid"] = "b7579f10-4a66-11e4-84f4-6953f0fa3715"
                 p["payload"] = { 'on':'true', 'color':'purple'}
                 response = skynet.triggerWebhook(p["uuid"], p["payload"])
        splunk.Intersplunk.outputResults(results)
        exit(0)
except Exception, e:
        h = ["ERROR"]
        results = [ {"ERROR": e} ]
        print "%s"%e
        exit(-1)
