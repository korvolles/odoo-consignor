# -*- coding: utf-8 -*-
{
    'name': "Consignor Shipping",
    'description': "Send your shippings through Consignor and track them online",
    'author': "TinderBox AS",
    'website': "http://tinderbox.no",
    'category': 'Sales Management',
    'version': '1.1',
    'depends': ['delivery', 'mail', 'stock'],
    'data': [
        'data/delivery_consignor.xml',
        'views/delivery_consignor.xml',
    ],
    'application': True,
    'installable': True,
}
