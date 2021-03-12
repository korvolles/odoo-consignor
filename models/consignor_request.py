# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import binascii, logging, os, suds, urllib, gzip, requests, json
from datetime import datetime
from suds.client import Client

_logger = logging.getLogger(__name__)
# uncomment to enable logging of SOAP requests and responses
# logging.getLogger('suds.client').setLevel(logging.DEBUG)

class ConsignorRequest():
    """ Low-level object intended to interface Odoo recordsets with Consignor,
        through appropriate SOAP requests """

    def loadactor(self, actor_id, key):
        res = []

        url = "http://sstest.consignor.com/ship/ShipmentServerModule.dll"
        values = {'actor': 63,
                  'key': "sample",
                  'command': 'GetProducts'}
        data = urllib.parse.urlencode(values).encode("utf-8")
        req = urllib.request.Request(url)
        try:
            resp = urllib.request.urlopen(req,data=data)
        except StandardError:
            print("error connecting to Consignor")
            return False

        return res
