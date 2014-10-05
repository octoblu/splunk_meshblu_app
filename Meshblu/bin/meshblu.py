from MeshbluClass import *

import sys, os, platform, re
import xml.dom.minidom, xml.sax.saxutils
import logging
import urllib2
import json, datetime
import sched, time
from datetime import datetime, date, time
from time import gmtime, strftime, localtime,mktime

import splunk.entity as entity

#set up logging suitable for splunkd comsumption
logging.root
logging.root.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.root.addHandler(handler)

_MI_APP_NAME = 'Meshblu'
_SPLUNK_HOME = os.getenv("SPLUNK_HOME")
if _SPLUNK_HOME == None:
    _SPLUNK_HOME = os.getenv("SPLUNKHOME")
if _SPLUNK_HOME == None:
    _SPLUNK_HOME = "/opt/splunkbeta"    

_OPERATING_SYSTEM = platform.system()
_APP_HOME = _SPLUNK_HOME + "/etc/apps/Meshblu/"
_LIB_PATH = _APP_HOME + "bin/lib/"
_PID = os.getpid()
_IS_WINDOWS = False

if _OPERATING_SYSTEM.lower() == "windows":
    _IS_WINDOWS = True
    _LIB_PATH.replace("/","\\")
    _APP_HOME.replace("/","\\")
    
#sys.path.insert(0,_LIB_PATH) - Only Needed if importing local libraries

#SYSTEM EXIT CODES
_SYS_EXIT_GPARENT_PID_ONE = 8
_SYS_EXIT_FAILED_VALIDATION = 7

#necessary to allow unbuffered writing for the Splunk Indexer
class Unbuffered:
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)
    
SCHEME = """<scheme>
    <title>Meshblu</title>
    <description>Commmunicate with a Meshblu Instance</description>
    <use_external_validation>true</use_external_validation>
    <streaming_mode>xml</streaming_mode>
    <endpoint>
        <args>
            <arg name="operation">
                <title>Endpoint Operation</title>
                <description>What endpoint to use. Valid choices: mydevices, status, messages</description>
            </arg>
            <arg name="device_uuid">
                <title>Device UUID</title>
                <description>Optional: The device UUID to interact with.</description>
            </arg>
            <arg name="device_token">
                <title>Device Token</title>
                <description>Optinoal: The device token to use for authentication.</description>
            </arg>
        </args>
    </endpoint>
</scheme>
"""

def do_scheme():
    """ Prints the Scheme """
    doPrint(SCHEME)

def get_source(config):
    return "meshblu:" + config
        
def print_error(s):
    """ print any errors that occur """
    doPrint("<error><message>%s</message></error>" % escape(s))
    logging.error(s)

def validate_conf(config, key):
    """ Validate that required key is in the config as parsed from stdin """
    if key not in config:
        raise Exception, "Invalid configuration received from Splunk: key '%s' is missing." % key

def getCredentials(sessionKey):
	myapp = 'Meshblu'
	try:
		#entities = entity.getEntities(['meshbluep','config'], namespace=myapp, owner='nobody', sessionKey=sessionKey)
		logging.info("placeholder")
	except Exception, e:
		raise Exception("Could not get %s credentials from splunk. Error: %s"
                      % (myapp, str(e)))
	#for i, c in entities.items():
        #	return c['meshblu_server'], c['server_uuid'], c['server_token']
	return "skynet.im:80", "5d6e9c91-820e-11e3-a399-f5b85b6b9fd0", "579nuups9k2lc8frglf6wnfwryue4s4i"
	raise Exception("No credentials have been found")  

#read XML configuration passed from splunkd
def get_config():
    """ Read XML Configuration data passed from splunkd on stdin """
    config = {}
    try:
        # read everything from stdin
        config_str = sys.stdin.read()
        logging.debug(config_str)
        # parse the config XML
        doc = xml.dom.minidom.parseString(config_str)
        root = doc.documentElement
        config['sessionKey'] = root.getElementsByTagName("session_key")[0].firstChild.nodeValue
        logging.debug("::%s::"%config['sessionKey'])
        conf_node = root.getElementsByTagName("configuration")[0]
        if conf_node:
            logging.debug("XML: found configuration")
            stanza = conf_node.getElementsByTagName("stanza")[0]
            if stanza:
                stanza_name = stanza.getAttribute("name")
                if stanza_name:
                    logging.debug("XML: found stanza " + stanza_name)
                    config["name"] = stanza_name

                    params = stanza.getElementsByTagName("param")
                    for param in params:
                        param_name = param.getAttribute("name")
                        logging.debug("XML: found param '%s'" % param_name)
                        if param_name and param.firstChild and \
                           param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                            data = param.firstChild.data
                            config[param_name] = data
                            logging.debug("XML: '%s' -> '%s'" % (param_name, data))

        if not config:
            raise Exception, "Invalid configuration received from Splunk."

        # just some validation: make sure these keys are present (required)
        validate_conf(config, "operation")
    except Exception, e:
        raise Exception, "Error getting Splunk configuration via STDIN: %s" % str(e)

    return config

def get_validation_data():
    val_data = {}
    # read everything from stdin
    val_str = sys.stdin.read()
    # parse the validation XML
    doc = xml.dom.minidom.parseString(val_str)
    root = doc.documentElement
    logging.debug("XML: found items")
    item_node = root.getElementsByTagName("item")[0]
    if item_node:
        logging.debug("XML: found item")
        name = item_node.getAttribute("name")
        val_data["stanza"] = name
        params_node = item_node.getElementsByTagName("param")
        for param in params_node:
            name = param.getAttribute("name")
            logging.debug("Found param %s" % name)
            if name and param.firstChild and \
               param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                val_data[name] = param.firstChild.data
    return val_data

def validate_arguments():
    val_data = get_validation_data()
    try:  
        if val_data["operation"] not in ["status", "mydevices", "messages"]:
                raise Exception, "API Feature '%s' not supported"%str(val_data["operation"])

    except Exception, e:
        print_error("Invalid configuration specified: %s" % str(e))
        sys.exit(_SYS_EXIT_FAILED_VALIDATION)
        
def daterange(start_date, end_date):
    for n in range(int ((end_date - start_date).days+1)):
        yield start_date + timedelta(n)

def doPrint(s):
    """ A wrapper Function to output data by same method (print vs sys.stdout.write)"""
    sys.stdout.write(s)

def escape(s):
    """ A wrapper function to force conformity on xml escaping, and for ease of reading """
    return xml.sax.saxutils.escape(s)

def do_event(string, sourcetype, source):
    """ Outputs a single broken event to the Splunk Processor """
    if len(string) < 1:
        string = "empty_event"
    string = escape(string)
    dostr = "<event><data>%s</data><source>%s</source><sourcetype>%s</sourcetype></event>" %(re.sub(r"[\r\n]+"," ",string), escape(source), escape(sourcetype))
    doPrint(dostr)    
    
def do_done_event(sourcetype, source):
    """ Outputs a single done even for an unbroken event to the Splunk Processor """
    dostr = "<event><source>%s</source><sourcetype>%s</sourcetype><done/></event>" %(escape(source), escape(sourcetype))
    doPrint(dostr)
    
def init_stream():
    """ Sends the XML for starting a Stream """
    logging.debug("Setting up stream")
    doPrint("<stream>")
    
def end_stream():
    """ Sends the XML for ending a Stream """
    logging.debug("Ending Stream")
    doPrint("</stream>")
    
def addStamp(json):
	json["blutime"] = "%s"%(strftime("%a, %d %b %Y %H:%M:%S %Z", localtime()))
	return json

def run():
    """ The Main function that starts the action. The thread will sleep for however many seconds are configured via the Input. """
    sys.stdout = Unbuffered(sys.stdout)
    config = get_config()  
    server, uuid, token = getCredentials(config['sessionKey'])

    op = config["operation"]
    skynet = MeshbluAPI(server,uuid,token)
    stanza = config["name"]
    #source = get_source(stanza[(stanza.rfind("/")+1):])    
    sourcetype = get_source(config["operation"])
    source = "meshblu" 
    init_stream()    
    if not _IS_WINDOWS:
            gparent_pid = os.popen("ps -p %d -oppid="%(os.getppid()) ).read().strip()
            if gparent_pid == 1:
                print_error("Whoa. That process shouldn't be like that.")
                sys.exit(_SYS_EXIT_GPARENT_PID_ONE)
    logging.info("source=%s sourcetype=%s stanza=%s operation=running_api"%(source,sourcetype,stanza))
    try:
         if (op == "status"):
         	do_event("%s"%(skynet.getStatus()),sourcetype,source)
         	do_done_event(sourcetype,source)
         elif (op == "mydevices"):
                myDevices = json.loads(skynet.getMyDevices())
		for dev in myDevices["devices"]:
               		do_event("%s"%(json.dumps(addStamp(dev))),sourcetype,source)
                do_done_event(sourcetype,source)
         else:
                raise Exception("API NOT DEFINED")
    except Exception, e: print_error("Exception in RunAPI call: %s"%e)
    end_stream()
    

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scheme":
            do_scheme()
        elif sys.argv[1] == "--validate-arguments":
            validate_arguments()
        elif sys.argv[1] == "--test":
            doPrint('No tests for the scheme present')
        else:
            doPrint('You giveth weird arguments')
    else:
        run()

    sys.exit(0)
