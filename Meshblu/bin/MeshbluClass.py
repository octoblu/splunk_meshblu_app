import logging, urllib2, sys, json, time, re, urllib
'''
Class MeshBlu API
Author: Kyle Smith
Email: kylesmith@kyleasmith.info
Copyright 2014
'''
def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        excpetions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            try_one_last_time = True
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                    try_one_last_time = False
                    break
                except ExceptionToCheck, e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print msg
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            if try_one_last_time:
                msg = "%s, Final Try with %d seconds..." % (str(e), mdelay)
                if logger:
                    logger.warning(msg)
                else:
                    print msg
                return f(*args, **kwargs)
            return
        return f_retry  # true decorator
    return deco_retry

class MeshbluAPI:
    WEBHOOK_BASE = "https://app.octoblu.com/api/webhooks/"
    API_URLS = {  "devices" : 		"/devices",
                  "status": 		"/status",
                  "mydevices" : 	"/mydevices",
                  "communicate": 	"/devices/%(uuid)",
                  "messages" : 		"/messages",
                  "ipaddress":		"/ipaddress",
                  "data": 		"/data/",
                  "subscribe" : 	"/subscribe/"
                  }
    conf = {}
    
    
    def __init__(self, server, skynet_auth_uuid, skynet_auth_token):
        """Construct an instance of the MeshbluAPI."""
        logging.debug("Setting INIT")
        self.conf["skynet_auth_uuid"] = skynet_auth_uuid
        self.conf["skynet_auth_token"] = skynet_auth_token
        tmp = server.split(":")
        self.conf["server"] = tmp[0]
        self.conf["port"] = tmp[1]
        self.conf["headers"] = { "skynet_auth_token": skynet_auth_token, "skynet_auth_uuid": skynet_auth_uuid }
       
    def __getURL(self, urltype):
        logging.debug("Running Get Url")
        return "http://" + self.conf["server"] +":"+self.conf["port"] + self.API_URLS[urltype] % self.conf

    # GET API CALLS
    def getMyDevices(self):
        logging.debug("Running getMyDevices")
        return self.__doAPICall(self.__getURL("mydevices"),None, False)
 
    def getStatus(self):
        logging.debug("Running Status")
        return self.__doAPICall(self.__getURL("status"),None, False)

    def getIPAddress(self):
        logging.debug("Running IP Address")
        return self.__doAPICall(self.getURL("ipaddress"), None, False)

    def getDataDate(self, uuid, start, finish):
	logging.debug("Running Get DataDate")
	url = "%s%s?start=%s&finish=%s"%(self.__getURL("data"), uuid, start, finish)
	return self.__doAPICall(url, None, False)

    # RETURNS A STREAM OBJECT   
    def getDataStream(self, uuid):
	logging.debug("Running Get Data Stream")
	url = "%s%s?stream=true"%(self.__getURL("data"), uuid)
	return self.__doAPICall(url, None, True)

    def subscribe(self, uuid):
	logging.debug("Running Subscribe Stream")
	url = self.__getURL("subscribe") + uuid
	return self.__doAPICall(url, None, True)

    # POST API CALLS
    def sendMessage(self, devices, payload):
        logging.debug("Running Send Message")
        data = { "devices": devices, "payload": payload }
        return self.__doAPICall(self.__getURL("messages"), data, False)

    def triggerWebhook(self, uuid, payload):
	logging.debug("Running Send web hook")
	url = self.WEBHOOK_BASE + uuid
        return self.__doAPICall(url, payload, False)

    def __makeError(self,s):
        logging.debug("Making an Error")
        raise Exception, "%s" % s
        
    @retry(urllib2.URLError, tries=15, delay=2, backoff=2, logger=logging)
    def __urlopen_with_retry(self, url):
        logging.debug("urlopen_with_retry")
        logging.debug("URL: %s"%url)
        urlRequest = urllib2.Request(url, headers=self.conf["headers"])
        return urllib2.urlopen(urlRequest)

    def __urlopen_with_retryPost(self, url, data):
        logging.debug("urlopen_with_retry_post")
        logging.debug("URL: %s"%url)
        method = "POST"
        d = urllib.urlencode(data)
	d = json.dumps(data)
        urlRequest = urllib2.Request(url, d,self.conf["headers"])
        urlRequest.get_method = lambda: method
        return urllib2.urlopen(urlRequest)

    def __doAPICall(self, url, data, streaming):
        logging.debug("Making an API CALL")
        if url == None:
            self.__makeError("Unable to get valid URL")
        logging.info("class=Meshblu.py url=\"%s\""%(url))
        defaultReturn = '{"not_assigned":"not_assigned"}'
        try: 
            f = None
            if streaming:
                  if data == None:
                     defaultReturn = self.__urlopen_with_retry(url)
                  else:
                     defaultReturn = self.__urlopen_with_retryPost(url, data)
            else:
                  if data == None:
                     f = self.__urlopen_with_retry(url)
                  else:
                     f = self.__urlopen_with_retryPost(url, data)
                  logging.debug("Urlopen Returned without Error")
                  defaultReturn = f.read()
                  f.close()
        except Exception, e:
            defaultReturn = "{\"permanent_url_error\":\"%s\"}"%(str(e));
        logging.debug("returing either json or stream")
        return defaultReturn
