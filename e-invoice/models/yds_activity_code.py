# -*- coding: utf-8 -*-

from odoo import models, fields, api


class YDSActivityCode(models.Model):
    _name = 'account.tax.activity.code'
    _description = 'pre-defined codes for activity types given my the egyptian government'
    name = fields.Char(string="Name", required=True)
    arabic_name = fields.Char(string="Arabic Name", required=True)
    code = fields.Char(string="Code", required=True)


