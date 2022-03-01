# -*- coding: utf-8 -*-
{
    'name': "YDS E-invoice",

    'summary': """Integration with egyptian e-invoice sdk""",

    'description': """
        module for managing e-invoice documents , generating signature from YDS provided app 
    """,
    'author': "yds-int (Omar Yasser)",
    'website': "http://www.yds-int.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'alpha',
    'version': '0.1',
    'sequence': -10,
    # any module necessary for this one to work correctly
    'depends': ['base','account','sale', 'uom'],
    'assets': {
        'web.assets_backend': [
            'e-invoice/static/src/css/yds_e-invoice.css',
            'e-invoice/static/src/css/yds_sync_einvoice.js'
        ],},
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/yds_account_tax_activity_code.xml',
        'views/yds_company.xml',
        'views/yds_company_branches_view.xml',
        'views/yds_account_journal_view.xml',
        'views/yds_cancel_einvoice_wizard.xml',
        'views/yds_einvoice_actions.xml',
        'views/yds_partner.xml',
        'views/yds_product_views.xml',
        'views/yds_invoice.xml',
        'views/yds_uom_views.xml',
        'views/yds_account_tax_views.xml',
        'views/yds_product_views.xml',
        'views/yds_invalid_status_views_wizard.xml',
        'data/yds_account_tax_type_data.xml',
        'data/yds_account_tax_activity_data.xml',
        'data/yds_uom_data.xml',
        
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}
