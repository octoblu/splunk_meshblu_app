#   Version 4.0
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

##  PERFORM MESHBLU API FUNCTIONS
##  ARGS op 
##  DEFAULTS = status _raw
##

help = """------------------------------------------------------------------------------------
MESHBLU HELP
------------------------------------------------------------------------------------"""

contexthelp = """------------------------------------------------------------------------------------
MESHBLU HELP
------------------------------------------------------------------------------------"""



def blu(results, settings):
	resultcount = len(results)
	server, skynet_auth_uuid, skynet_auth_token = getCredentials(settings)
	skynet = MeshbluAPI(server, skynet_auth_uuid, skynet_auth_token)
	op = "status"
	output_field = "meshblu_response"
        for res in results:
		op = res["operation"]
		if op not in ['status', 'webhook', 'message']:
			return splunk.Intersplunk.generateErrorResults("op=%s is not supported" % op)
		if op == "status":
			res[output_field] = skynet.getStatus()
		elif op == "mydevices":
			res[output_field] = skynet.getMyDevices()
		elif op == "message":
			res[output_field] = skynet.sendMessage(res["uuid"],res["payload"])
		elif op == "webhook":
			res[output_field] = skynet.triggerWebhook(res["uuid"], res["payload"])
	return results

results = []
(isgetinfo, sys.argv) = splunk.Intersplunk.isGetInfo(sys.argv)

def getCredentials(settings):
        myEnt = entity.getEntity('/meshbluep/config','config', namespace='Meshblu',sessionKey=settings['sessionKey'], owner='nobody')
        return myEnt.get('meshblu_server'), myEnt.get('server_uuid'), myEnt.get('server_token')
    
try:
    # poor mans opt
    for a in sys.argv[1:]:

        # This (old) feature just put a 'help' header for people who don't know
        # how to read diff
        # Commenting out for now since the header has been put into the decorations stuff.
        if a.startswith("op="):
            where = a.find('=')
            op = a[where+1:len(a)]

        elif isgetinfo:
            splunk.Intersplunk.parseError("Invalid argument '%s'" % a)

    if isgetinfo:
        splunk.Intersplunk.outputInfo(False, False, True, False, None, False)

    settings = dict()
    results = splunk.Intersplunk.readResults(settings=settings, has_header=True)
    results = blu(results, settings)

except Exception, e:
    import traceback
    stack =  traceback.format_exc()
    if isgetinfo:
        splunk.Intersplunk.parseError(str(e))
        
    results = splunk.Intersplunk.generateErrorResults(str(e))
    logger.warn("invalid arguments passed to 'blu' search operator. Traceback: %s" % stack)

splunk.Intersplunk.outputResults(results)
