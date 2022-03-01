from odoo import models, fields, api


class YDSUoM(models.Model):
    _inherit = 'uom.uom'
    code = fields.Char(string = "Code" ,default="EA")