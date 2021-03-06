# -*- coding: utf-8 -*-
# TinderBox AS - Addon, See LICENSE file for full copyright and licensing details.
import logging, urllib, gzip, requests, json, csv, os, tempfile
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from . import consignor_request
from ppretty import ppretty

_logger = logging.getLogger(__name__)

class ProviderConsignor(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('consignor', "Consignor")], ondelete={'consignor': 'cascade'})

    # TODO Set the needed properties for interacting with the Consignor API
    consignor_server_url = fields.Char(string="Server URL")
    consignor_server_key = fields.Char(string="Key")
    consignor_actor_id = fields.Char(string="Account ID")
    consignor_categ_id = fields.Many2one('product.category', ondelete='cascade')
    consignor_test_mode = fields.Boolean(default=True, string="Test Mode", help="Uncheck this box to use production Consignor Web Services")

    # This was removed in Odoo 10, but is used by this plugin
    partner_id = fields.Many2one('res.partner', string='Transporter Company', help="The partner that is doing the delivery service.")
    consignor_product_prod_csid = fields.Integer(related="product_id.consignor_product_prod_csid", string="Product CSID")

    def load_consignor_actor(self):
        _logger.info("load_consignor_actor")

        url = self.consignor_server_url
        values = {'actor': self.consignor_actor_id,
                  'key': self.consignor_server_key,
                  'command': 'GetProducts'}
        data = urllib.parse.urlencode(values).encode("utf-8")
        response = requests.get(url, data=data)

        # import pdb;pdb.set_trace()
        ### Testing Purpose ###
        # Simulator URL: http://consignorsupport.no/testbench/ShipmentServer.aspx
        # values1 = {'actor': "63",
        #           'key': "sample",
        #           'command': 'GetProducts'}
        # data1 = urllib.parse.urlencode(values).encode("utf-8")
        # url1 = "http://sstest.consignor.com/ship/ShipmentServerModule.dll"
        # response = requests.get(url1, data=data1)

        res = response.json()

        # Reading the Carriers information
        for Carrier in res.get('Carriers'):
            carrier_partner_id = self.insert_update_carrier(Carrier)

            # Reading the SubCarrier information - This is the high level services offered by the Carrier
            for SubCarrier in Carrier['Subcarriers']:
                sub_carrier_csid = SubCarrier['SubcarrierCSID']
                try:
                    sub_carrier_concept_id = SubCarrier['SubcarrierConceptID']
                except KeyError:
                    sub_carrier_concept_id = None
                sub_carrier_name = SubCarrier['SubcarrierName']
                _logger.info(str(sub_carrier_name))

                # Reading the product information within each service offered by the Carrier
                for Product in SubCarrier['Products']:
                    product_prod_csid = Product['ProdCSID']
                    try:
                        product_prod_concept_id = Product['ProdConceptID']
                    except KeyError:
                        product_prod_concept_id = None

                    product_prod_name = Product['ProdName']
                    _logger.info("  - " + str(product_prod_name))

                    if not self.consignor_test_mode:
                        # Now we are able to create the delivery product in Odoo
                        delivery_product = self.env['product.product'].search([('consignor_sub_carrier_csid', '=',
                                                                                 sub_carrier_csid), ('consignor_product_prod_csid', '=', product_prod_csid )])
                        if not delivery_product:
                            _logger.info("Insert product")
                            vals = {
                                'name': sub_carrier_name + " - " + product_prod_name,
                                'type': 'service',
                                'invoice_policy': 'order',
                                'purchase_method': 'receive',
                                'list_price': 0.00,
                                'consignor_sub_carrier_csid': sub_carrier_csid,
                                'consignor_product_prod_csid': product_prod_csid
                            }
                            delivery_product = self.env['product.product'].create(vals)
                            delivery_product_supplier = self.env['product.supplierinfo'].create({'name': carrier_partner_id,
                                                                                              'company_id': 1,
                                                                                              'product_id': delivery_product.id})

                        else:
                            _logger.info("Update product")
                            vals = {
                                'name': sub_carrier_name + " - " + product_prod_name,
                                'type': 'service',
                                'invoice_policy': 'order',
                                'purchase_method': 'receive',
                                'consignor_sub_carrier_csid': sub_carrier_csid,
                                'consignor_product_prod_csid': product_prod_csid
                            }
                            delivery_product.write(vals)

                        # Insert or update the Delivery product in Delivery Carrier model
                        delivery_carrier = False
                        try:
                          delivery_carrier = self.env['delivery.carrier'].search([('product_id', '=', delivery_product.id),
                                                                                  ('partner_id', '=', carrier_partner_id)])
                          # break
                        except ValueError:
                          _logger.info('product_id not found')

                        if not delivery_carrier:
                            _logger.info("Insert carrier")
                            vals = {
                                'name': sub_carrier_name,
                                'delivery_type': 'consignor',
                                'product_id': delivery_product.id,
                                'partner_id': carrier_partner_id,
                                'consignor_server_url': self.consignor_server_url,
                                'consignor_server_key': self.consignor_server_key,
                                'consignor_actor_id': self.consignor_actor_id
                            }
                            delivery_carrier = self.env['delivery.carrier'].create(vals)
                            _logger.info(delivery_carrier.id)
                        else:
                            _logger.info("Delivery carrier update")
                            vals = {
                                'name': sub_carrier_name,
                                'delivery_type': 'consignor',
                                'product_id': delivery_product.id,
                                'partner_id': carrier_partner_id,
                                'consignor_server_url': self.consignor_server_url,
                                'consignor_server_key': self.consignor_server_key,
                                'consignor_actor_id': self.consignor_actor_id
                            }
                            delivery_carrier.write(vals)


        return []

    def insert_update_carrier(self,Carrier=[]):
        # Insert or update the Carrier information in res.partner model
        carrier_partner = self.env['res.partner'].search([('consignor_carrier_csid', '=', Carrier['CarrierCSID'])])
        if not carrier_partner:
            _logger.info("Insert " + str(Carrier['CarrierFullName']))
            vals = {
                'company_type': 'company',
                'name': Carrier['CarrierFullName'],
                'consignor_carrier_csid': Carrier['CarrierCSID'],
                'consignor_carrier_full_name': Carrier['CarrierFullName'],
                'consignor_carrier_short_name': Carrier['CarrierShortName']
            }
            if not self.consignor_test_mode:
                carrier_partner = self.env['res.partner'].create(vals)
                _logger.info(carrier_partner.id)
        else:
            _logger.info("Update " + str(Carrier['CarrierFullName']))

        return carrier_partner.id

    def consignor_rate_shipment(self, orders):
        return {
            "success": True,
            "price": self.product_id.list_price,
            "error_message": False,
            "warning_message": False,
        }

    def consignor_send_shipping(self, pickings):
        # Save Shipment or Submit Shipment?
        # If Save Shipment, implement a new Status,
        res = []

        for picking in pickings:
            _logger.info("Creating Consignor shipment for picking " + str(picking.id) + " (" + str(picking.name) + ")")

            # _logger.info(ppretty(picking.carrier_id, seq_length=25))

            senderAddress = {}
            senderAddress['Kind'] = '2'
            senderAddress['Name1'] = picking.company_id.name
            senderAddress['Street1'] = picking.company_id.street
            senderAddress['Street2'] = picking.company_id.street2 or ""
            senderAddress['PostCode'] = picking.company_id.zip
            senderAddress['City'] = picking.company_id.city
            senderAddress['CountryCode'] = picking.company_id.country_id.code

            receiverAddress = {}
            receiverAddress['Kind'] = '1'
            receiverAddress['Name1'] = picking.partner_id.name
            receiverAddress['Street1'] = picking.partner_id.street
            receiverAddress['Street2'] = picking.partner_id.street2 or ""
            receiverAddress['PostCode'] = picking.partner_id.zip
            receiverAddress['City'] = picking.partner_id.city
            receiverAddress['CountryCode'] = picking.partner_id.country_id.code
            receiverAddress['Mobile'] = picking.partner_id.mobile or picking.partner_id.phone or ""
            receiverAddress['Email'] = picking.sale_id.partner_id.email or picking.partner_id.email

            lines = [
               {
                "PkgWeight": int(_convert_weight(picking.shipping_weight, "GR")) or 1000,
                "Pkgs": [
                    {"ItemNo": 1}
                ]
               }
            ]

            submitshipment_data = {}
            submitshipment_data['OrderNo'] = picking.origin
            submitshipment_data['Kind'] = '1'
            submitshipment_data['ActorCSID'] = self.consignor_actor_id
            submitshipment_data['ProdCSID'] = picking.carrier_id.consignor_product_prod_csid
            #submitshipment_data['Addresses'] = '[' + json.dumps(receiverAddress) + ']'
            #submitshipment_data['Addresses'] = '[' + json.dumps(senderAddress) + '],[' + json.dumps(receiverAddress) + ']'
            submitshipment_data['Addresses'] = [senderAddress, receiverAddress]
            submitshipment_data['Lines'] = lines

            submitshipment_data['References'] = [
                {
                    "Kind" : 53,
                    "Value" : "Z1"
                },
                {
                    "Kind" : 257,
                    "Value" : "Z1_doc" 
                }
            ]

            json_data = json.dumps(submitshipment_data)
            _logger.info("Saving shipment to Consignor")
            _logger.info(json_data.encode('UTF-8'))

            url = self.consignor_server_url
            values = {'actor': self.consignor_actor_id,
                      'key': self.consignor_server_key,
                      'command': 'SubmitShipment',
                      'data': json_data,
                      'options': '{"Labels": "none", "UseLocalPrint": "1"}'}

            data = urllib.parse.urlencode(values).encode("utf-8")
            response = requests.get(url, data=data)

            # _logger.info(response.text)
            js_res = json.loads(response.text)

            if "ErrorMessages" in js_res:
                raise UserError("Error message from Consignor: " + ", ".join(js_res["ErrorMessages"]))

            tmpTracking = ""
            try:
              tmpTracking = js_res["Lines"][0]["Pkgs"][0]["PkgNo"]
            except:
              _logger.info("No PkgNo found")

            try:
              tmpTracking = js_res["ShpNo"]
            except:
              _logger.info("No ShpNo found")

            _logger.info(tmpTracking)

            res = res + [{'tracking_number': tmpTracking, 'exact_price': self.product_id.list_price}]

            # Dir = tempfile.mkdtemp()
            # tmp_dir = os.path.join(Dir, "export")
            # os.mkdir(tmp_dir)

            # report_name = picking.origin + ".csv"
            # report_dir = os.path.join("/tmp", report_name)

            filename = str(picking.id)
            if picking.origin:
                filename = (picking.origin).replace("/","_")
            else:
                filename = (picking.name).replace("/","_")
            
            with open('/odoo/export/' + filename + '.csv', "w", newline="") as f:
                fieldnames = ['name', 'street', 'street2', 'postcode', 'city', 'countrycode', 'email', 'mobile', 'ordernumber', 'shipmentid', 'carrier', 'shippingproduct', 'weight', 'consignorid', 'trackingreference']
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerow({
                    'name': picking.partner_id.name.encode('ISO 8859-1'),
                    'street': picking.partner_id.street.encode('ISO 8859-1'),
                    'street2': picking.partner_id.street2 and picking.partner_id.street2.encode('ISO 8859-1') or "",
                    'postcode': picking.partner_id.zip.encode('ISO 8859-1'),
                    'city': picking.partner_id.city.encode('ISO 8859-1'),
                    'countrycode': picking.partner_id.country_id.code.encode('ISO 8859-1'),
                    'email': (picking.sale_id.partner_id.email or picking.partner_id.email).encode('ISO 8859-1'),
                    'mobile': (picking.partner_id.mobile or picking.partner_id.phone or "").encode('ISO 8859-1'),
                    'ordernumber': picking.origin.encode("ISO 8859-1"),
                    'shipmentid': picking.name.encode("ISO 8859-1"),
                    'carrier': self.name.encode("ISO 8859-1"),
                    'shippingproduct': self.product_id.name.encode("ISO 8859-1"),
                    'weight': int(_convert_weight(picking.shipping_weight, "GR")) or 1000,
                    'consignorid': js_res["ShpCSID"],
                    'trackingreference': tmpTracking.encode("ISO 8859-1")
                })
            # shutil.rmtree(Dir, ignore_errors=False, onerror=None)

#        print json.dumps(res).encode("UTF-8")
        return res

    def consignor_get_tracking_link(self, pickings):
        res = []
        return res

    def consignor_cancel_shipment(self, picking):
        res = []
        return res


def _convert_weight(weight, unit='KG'):
    ''' Convert picking weight (always expressed in KG) into the specified unit '''
    if unit == 'KG':
        return weight
    elif unit == 'GR':
        return weight * 1000.0
    else:
        raise ValueError
