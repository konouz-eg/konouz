from odoo import models, fields, api


class YDSAccountTax(models.Model):
    _inherit = 'account.tax'
    arabic_name = fields.Char(string="Arabic Name")
    code = fields.Char(string="Code")
    tax_type = fields.Selection(string='E-Invoice Tax Type', selection=[(
        'taxable', 'Taxable'), ('non_taxable', 'Non-Taxable')])
    subtype_name = fields.Char(string="Name")
    subtype_arabic_name = fields.Char(string="Arabic Name")
    subtype_code = fields.Char(string="Code")
    country_id = fields.Many2one(related="company_id.country_id")
    description = fields.Char(
        string='Label on Invoices', compute='_compute_label')

    @api.onchange('name', 'subtype_name')
    @api.depends('name', 'subtype_name')
    def _compute_label(self):
        for record in self:
            if record.name and record.subtype_name:
                record.description = record.name+' ('+record.subtype_name+')'
            else:
                record.description = False

    def name_get(self):
        name_list = []
        type_tax_use = dict(
            self._fields['type_tax_use']._description_selection(self.env))
        tax_scope = dict(
            self._fields['tax_scope']._description_selection(self.env))
        for record in self:
            name = record.name
            if self._context.get('append_type_to_tax_name'):
                name += ' (%s)' % type_tax_use.get(record.type_tax_use)
            if record.tax_scope:
                name += ' (%s)' % tax_scope.get(record.tax_scope)
            if record.subtype_name:
                name += ' (%s)' % record.subtype_name
            name_list += [(record.id, name)]
        return name_list
