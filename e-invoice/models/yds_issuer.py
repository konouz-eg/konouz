# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
from .yds_einvoice_api import EinvoiceMixin

class Branch(models.Model):
    _name = 'issuer.branch'

    
    company_id = fields.Many2one(comodel_name='res.company', string='Company')
    branch_id = fields.Char(string="Branch Number(Unique)")
    _sql_constraints = [ ('unique_branch', 'unique(company_id, branch_id)', 'Cannot Use same branch for company!\nPlease, select a add another branch')	]
    regionCity = fields.Char(string = "City")
    state_id = fields.Many2one(
        'res.country.state', string="Governate", domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string="Country")
    street = fields.Char(string = "Street")
    building_number = fields.Char(string="Building Number")

    postalCode = fields.Char(string = "Postal Code")
    floor = fields.Char(string="Floor")
    room = fields.Char(string="Room")
    landmark = fields.Char(string="Landmark")
    additional_information = fields.Char(string="Additional Information")

    def name_get(self):
        name_list = []
        for record in self:
            name = str(record.branch_id) + '/' +  str(record.country_id.name) + '/' +  str(record.state_id.name) + '/' +  record.regionCity + '/' +  record.street + '/' +  record.building_number
            name_list += [(record.id, name)]
        return name_list

    def prepare_branch_address_json(self):
        for record in self:
            address = {
                "country": record.country_id.code,
                "governate": record.state_id.name,
                "regionCity": record.regionCity,
                "street": record.street,
                "buildingNumber": record.building_number
            }
            if record.company_id.issuer_type == 'B':
                address["branchID"]=record.branch_id
            elif record.branch_id:
                address["branchID"]=record.branch_id
            if record.postalCode:
                address["postalCode"] = record.postalCode
            if record.floor:
                address['floor'] = record.floor
            if record.room:
                address["room"] = record.room
            if record.landmark:
                address["landmark"] = record.landmark
            if record.additional_information:
                address["additionalInformation"] = record.additional_information
            return address
class Issuer(models.Model):
    _name = 'res.company'
    _inherit = ['einvoice.mixin','res.company','signature.api']
    issuer_type = fields.Selection(string='Tax Issuer Type', selection=[(
        'B', 'Business'), ('P', 'Person'), ('F', 'Foreigner')], default='B')
    # vat in the res.company is the id
    # name in the res.company is the name
    client_id = fields.Char(string="Client Id")
    client_secret = fields.Char(string="Client Secret")
    token = fields.Char(string="E-invoice Token")
    environment = fields.Selection(string='Environment', selection=[(
        'uat', 'UAT/PREPROD'), ('prod', 'PRODUCTION')])
        #, ('sit', 'SIT')
    api_base_url = fields.Char(default="https://api.preprod.invoicing.eta.gov.eg")
    id_srv_base_url = fields.Char(default="https://id.preprod.eta.gov.eg")
    einvoice_login_status =fields.Selection(string='E-invoice Loggin', selection=[('logged_out', 'Logged Out'),
        ('logged_in', 'Logged in')] ,default='logged_out')
    # address
    branch_ids = fields.One2many(
        'issuer.branch', 'company_id', string='Branches', copy=False)
    branch_id = fields.Char(string="branchId")
    #country = fields.Char(string = "country")
    #governate = fields.Char(string="governate")
    #regionCity = city
    #regionCity = fields.Char(string = "regionCity")
    #street = street
    #street = fields.Char(string = "street")
    building_number = fields.Char(string="buildingNumber")
    # postalCode=zip
    #postalCode = fields.Char(string = "postalCode")
    floor = fields.Char(string="floor")
    room = fields.Char(string="room")
    landmark = fields.Char(string="landmark")
    additional_information = fields.Char(string="additionalInformation")

    activity_code_ids = fields.Many2many(
        comodel_name='account.tax.activity.code', string="Activity Codes")
    
    #these fields are used to connect to the 3rd party app for the usb token generated signature
    signature_ip = fields.Char()
    signature_port = fields.Char(default='9888')
    token_subject_name = fields.Char()
    sig_connect = fields.Boolean(default=False,readonly=True)

    @api.onchange('environment')
    def set_urls(self):
        for record in self:
            if(record.environment == 'uat'):
                record.api_base_url = 'https://api.preprod.invoicing.eta.gov.eg'
                record.id_srv_base_url = 'https://id.preprod.eta.gov.eg'
            # elif(record.environment == 'sit'):
            #     record.api_base_url = 'https://api.sit.invoicing.eta.gov.eg'
            #     record.id_srv_base_url = 'https://id.sit.eta.gov.eg'
            elif(record.environment == 'prod'):
                record.api_base_url = 'https://api.invoicing.eta.gov.eg'
                record.id_srv_base_url = 'https://id.eta.gov.eg'

    @api.depends('api_base_url')
    def login_request(self):
        for record in self:
            if record.client_id and record.client_secret:
                record.einvoice_loggin(record)
            if not record.client_id:
                raise ValidationError("Client ID is missing")
            if not record.client_secret:
                raise ValidationError("Client Secret is missing")


                # company.einvoice_login_status='logged_out'
        # print(self.api_base_url)
        # # return{
        # #     'type':'ir.actions.act_url',
        # #     'target':'self',
        # #     'url':self.api_base_url+'connect/token/'
        # # }
    def prepare_address_json(self,branch_id):
        for record in self:
            if not record.branch_ids or not branch_id:
                address = {
                    "country": record.country_id.code,
                    "governate": record.state_id.name,
                    "regionCity": record.city,
                    "street": record.street,
                    "buildingNumber": record.building_number
                }
                if record.issuer_type == 'B':
                    address["branchID"]=record.branch_id
                elif record.branch_id:
                    address["branchID"]=record.branch_id
                if record.zip:
                    address["postalCode"] = record.zip
                if record.floor:
                    address['floor'] = record.floor
                if record.room:
                    address["room"] = record.room
                if record.landmark:
                    address["landmark"] = record.landmark
                if record.additional_information:
                    address["additionalInformation"] = record.additional_information
                return address
            else:
                if branch_id:
                    #print("HERE")
                    return branch_id.prepare_branch_address_json()

    def prepare_issuer_json(self,branch_id):
        for record in self:
            issuer = {
                "address": record.prepare_address_json(branch_id) ,
                "type":record.issuer_type,
                "id":record.vat,
                "name":record.name,
            }
            #print(issuer["address"])
            return issuer

    def test_signature_connection(self):
        for record in self:
            if not record.signature_ip:
                raise ValidationError("Signature APP IP is missing")
            if not record.signature_port:
                raise ValidationError("Signature Port is missing")
            if not record.token_subject_name:
                raise ValidationError("Token Subject Name is missing")
            
            response_code =record.signature_test_connection(record.signature_ip,record.signature_port,record.token_subject_name)
            if response_code == 201:
                record.sig_connect=True
            elif response_code==204:
                record.sig_connect=False
                raise ValidationError("Subject name didn't match the certificate")
            elif response_code == 500:
                record.sig_connect=False
                raise ValidationError("Couldn't Reach Signature App")

                
