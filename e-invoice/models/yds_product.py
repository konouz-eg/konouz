from odoo import models, fields, api
import requests


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    item_type = fields.Selection(string='Item Type', selection=[
                                 ('GS1', 'GS1'), ('EGS', 'EGS')])
    item_code = fields.Char(string="Item Code")