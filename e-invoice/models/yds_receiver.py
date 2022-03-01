from odoo import models, fields, api


class Receiver(models.Model):
    _inherit = 'res.partner'
    is_person = fields.Boolean(string='Is a Person', default=False)
    is_foreign = fields.Boolean(string='Is a Foreigner', default=False)
    company_type = fields.Selection(selection_add=[('F', 'Foreigner')])
    universal_company_id = fields.Many2one('res.company', 'Company', index=True, compute="_set_universal_company") 
    # receiver_type = fields.Selection(string='Tax Receiver Type',selection=[('B', 'Business'), ('P', 'Person'),('F', 'Foreigner')] ,default = 'B')
    #vat in the res.company is the id
    #name in the res.company is the name
    company_activity_codes = fields.Many2many(
        related="universal_company_id.activity_code_ids")
    partner_activity_code = fields.Many2one(
        'account.tax.activity.code', string="Activity Code", domain="[('id', 'in', company_activity_codes)]")
    parent_partner_activity_code = fields.Many2one(
        'account.tax.activity.code', readonly=True, compute="_compute_parent_partner_activity_code")
    #address
    #country = fields.Char(string = "country")
    # governate = fields.Char(string = "governate")
    #regionCity = city
    #regionCity = fields.Char(string = "regionCity")
    #street = street
    #street = fields.Char(string = "street")
    building_number = fields.Char(string = "buildingNumber")
    #postalCode=zip
    #postalCode = fields.Char(string = "postalCode")
    floor = fields.Char(string = "floor")
    room = fields.Char(string = "room")
    landmark = fields.Char(string = "landmark")
    additional_information = fields.Char(string = "additionalInformation")


    def _set_universal_company(self):
        for record in self:
            record.universal_company_id=record.env.company.id

    @api.onchange('parent_id')
    def _compute_parent_partner_activity_code(self):
        for record in self:
            record.parent_partner_activity_code= None
            if record.parent_id:
                if record.parent_id.partner_activity_code:
                    record.parent_partner_activity_code = record.parent_id.partner_activity_code
                    record.partner_activity_code=record.parent_id.partner_activity_code

    @api.onchange('company_type')
    def onchange_company_type(self):
        for record in self:
            if record.company_type == 'person':
                record.is_company = False
                record.is_person = True
                record.is_foreign = False
            elif record.company_type == 'company':
                record.is_company = True
                record.is_person = False
                record.is_foreign = False
            else:  
                record.is_company = False
                record.is_person = False
                record.is_foreign = True

    @api.depends('is_company','is_person','is_foreign')
    def _compute_company_type(self):
        for record in self:
            if record.is_company:
                record.company_type = 'company' 
            elif record.is_person or (not record.is_company and not record.is_foreign):
                record.company_type = 'person'
            elif record.is_foreign: 
                record.company_type = 'F'

    def _write_company_type(self):
        for partner in self:
            if partner.company_type == 'person':
                partner.is_company = False
                partner.is_person = True
                partner.is_foreign = False
            elif partner.company_type == 'company':
                partner.is_company = True
                partner.is_person = False
                partner.is_foreign = False
            else:  
                partner.is_company = False
                partner.is_person = False
                partner.is_foreign = True

    def prepare_address_json(self):
        for record in self:
            address = {
                "country": record.country_id.code,
                "governate": record.state_id.name,
                "regionCity": record.city,
                "street": record.street,
                "buildingNumber": record.building_number,
            }
            if record.zip:
                address["postalCode"] = record.zip
            if record.floor:
                address["floor"] = record.floor
            if record.room:
                address["room"] = record.room
            if record.landmark:
                address["landmark"] = record.landmark
            if record.additional_information:
                address["additionalInformation"] = record.additional_information
            return address

    def prepare_receiver_json(self):
        for record in self:
            # receiver = { "address": record.prepare_address_json(),}
            receiver={}
            if record.company_type == "person":
                receiver["type"] = "P"
            elif record.company_type == "company":
                receiver["type"] = "B"
            elif  record.company_type == "F":
                receiver["type"] = "F"
            return receiver