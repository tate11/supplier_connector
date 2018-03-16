# -*- coding: utf-8 -*-
{
    'name': "Supplier Connector",

    'summary': """
        Supplier connector is a module for integration the supplier's products source on odoo
    """,

    'description': """
        Supplier connector is a module for integration the supplier's products source on odoo
    """,

    'author': "Halltic eSolutions S.L.",
    # 'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Purchase',
    'version': '0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['purchase', 'sale', 'product_margin', 'sale_stock', 'mrp', 'html_image_url_extractor'],

    # always loaded
    'data': [
        'data/supplier_scheduler.xml',
        'data/supplier_data.xml',
        'views/partner_view.xml',
        'views/importer_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
