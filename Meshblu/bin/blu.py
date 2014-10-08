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

def blu(results, settings):
	resultcount = len(results)
	server, skynet_auth_uuid, skynet_auth_token = getCredentials(settings)
	skynet = MeshbluAPI(server, skynet_auth_uuid, skynet_auth_token)
	op = "status"
	uuid = None
	payload = None
	output_field = settings["output_field"]
	uuid_field = settings["uuid_field"]
	operation_field = settings["operation_field"]
	payload_field = settings["payload_field"]
	wait_time = settings["wait"]
        for res in results:
		tmpResponse = None
		if operation_field in res:
			op = res[operation_field]
		if uuid_field in res:
			uuid = res[uuid_field]
		if payload_field in res:
			payload =json.loads(res[payload_field])
		if op not in ['status', 'webhook', 'message']:
			return splunk.Intersplunk.generateErrorResults("op=%s is not supported" % op)
		if op == "status":
			tmpResponse = skynet.getStatus()
		elif op == "mydevices":
			tmpResponse = skynet.getMyDevices()
		elif op == "message":
			if uuid_field not in res or payload_field not in res:
				return splunk.Intersplunk.generateErrorResults("payload and uuid must be defined for operation=%s"%op)
			tmpResponse = skynet.sendMessage(uuid, payload)
		elif op == "webhook":
                        if uuid_field not in res or payload_field not in res:
                                return splunk.Intersplunk.generateErrorResults("payload and uuid must be defined for operation=%s"%op)
			tmpResponse = skynet.triggerWebhook(uuid, payload)
		res[output_field] = tmpResponse
		if (wait_time > 0):
			time.sleep(wait_time)
	return results

results = []
(isgetinfo, sys.argv) = splunk.Intersplunk.isGetInfo(sys.argv)

def getCredentials(settings):
        myEnt = entity.getEntity('/meshbluep/config','config', namespace='Meshblu',sessionKey=settings['sessionKey'], owner='nobody')
        return myEnt.get('meshblu_server'), myEnt.get('server_uuid'), myEnt.get('server_token')
    
try:
    # poor mans opt
    # DEFAULTS
    settings = dict()
    settings["output_field"] = "blu_response"
    settings["payload_field"] = "blu_payload"
    settings["operation_field"] = "blu_operation"
    settings["uuid_field"] = "blu_uuid"
    settings["wait"] = 0
    for a in sys.argv[1:]:

        # This (old) feature just put a 'help' header for people who don't know
        # how to read diff
        # Commenting out for now since the header has been put into the decorations stuff.
        if a.startswith("output_field="):
            where = a.find('=')
            settings["output_field"] = a[where+1:len(a)]
	elif a.startswith("payload_field="):
		where = a.find('=')
		settings["payload_field"] = a[where+1:len(a)]
        elif a.startswith("operation_field="):
                where = a.find('=')
                settings["operation_field"] = a[where+1:len(a)]
        elif a.startswith("uuid_field="):
                where = a.find('=')
                settings["uuid_field"] = a[where+1:len(a)]
        elif isgetinfo:
            splunk.Intersplunk.parseError("Invalid argument '%s'" % a)

    if isgetinfo:
        splunk.Intersplunk.outputInfo(False, False, True, False, None, False)

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
