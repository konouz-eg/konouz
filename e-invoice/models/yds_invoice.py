import base64
from dataclasses import field
from datetime import date, datetime, timedelta
import time
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import re
from time import sleep
from .utils import einvoice_submit_document

_logger = logging.getLogger(__name__)
class Journal(models.Model):
    _inherit = 'account.journal'
    is_einvoice = fields.Boolean(default=False)

    

class YDSInvoiceLine(models.Model):
    _inherit = 'account.move.line'
    # item_type and item_code in product.template model
    item_code = fields.Char(
        related="product_id.product_tmpl_id.item_code", readonly=True)
    item_type = fields.Selection(
        related="product_id.product_tmpl_id.item_type", readonly=True)

    # description from account.move.line.name

    # unitType from account.move.line.product_uom_id.name should import unit types https://sdk.invoicing.eta.gov.eg/codes/unit-types/
    unit_type = fields.Char(related="product_uom_id.code")

    # quantity from account.move.line.quantity

    # unitValue -subDict
    # currencySold from res.company.currency_id.name must be imported according to ISO 4217 https://docs.1010data.com/1010dataReferenceManual/DataTypesAndFormats/currencyUnitCodes.html
    # amountEGP Price of unit of goods/services sold in EGP.  from account.move.line.price_unit
    # amountSold from account.move.line.price_unit if currencySold == EGP
    # currencyExchangeRate = 1.00000 if currencySold == EGP

    # Total amount for the invoice line considering quantity and unit price in EGP (with excluded factory amounts if they are present for specific types in documents).
    # 947 = QTY(5) * untPrice(189.4)
    sales_total = fields.Monetary(
        string="Sales Total(Q*P)", compute="_compute_sales_total")
    # Total amount for the invoice line after adding all pricing items, taxes, removing discounts.
    # 2969.89 = sum of taxableItems(2,269.83) +
    total = fields.Monetary(string="Total", compute="_compute_total")

    # Value difference when selling goods already taxed (accepts +/- numbers), e.g., factory value based.
    # default value to be revised
    value_difference = fields.Float(string="Value Difference", default=0.0)
    # Total amount of additional taxable fees to be used in final tax calculation.
    total_taxable_fees = fields.Monetary(
        string="Additional Taxable Fees", default=0.0)  # , compute="_compute_total")
    # Total amount for the invoice line after applying discount.
    # net_total = account.move.line_sub_total
    internal_code = fields.Char(
        string='Internal Code', compute='_compute_internal_code', store=True)
    items_discount = fields.Monetary(
        string='Non-Tax Items Discount(value)', digits='Discount')
    sum_taxable_items = fields.Monetary(
        compute='_compute_sum_taxable_items', default=0.0)
    discount_amount = fields.Monetary(default=0.0)

    @api.depends('sales_total', 'sum_taxable_items','items_discount')
    def _compute_total(self):
        for record in self:
            total = record.sum_taxable_items + \
                record.sales_total - \
                record.sales_total * (record.discount/100) -\
                record.items_discount
            record.total = ("{:.5f}".format(total))

    # items_discount = fields.Float(
        # string="Non-taxable items discount", readonly=True)
    @api.onchange('price_unit', 'quantity')
    def _compute_sales_total(self):
        for record in self:
            sales_total = record.quantity * record.price_unit
            record.sales_total = ("{:.5f}".format(sales_total))

    @api.depends('move_id', 'product_id')
    @api.onchange('move_id', 'product_id')
    def _compute_internal_code(self):
        for record in self:
            if record.product_id.default_code == False:
                record.internal_code = record.move_id.name + \
                    str(record.id) + 'R'
            else:
                record.internal_code = record.move_id.name \
                    + '/' + record.product_id.default_code \
                    + '/' + str(record.id) + 'R'

    @api.onchange('tax_ids')
    @api.constrains('move_id.journal_id.is_einvoice')
    def _check_tax_ids_codes(self):
        for record in self:
            if record.move_id.journal_id.is_einvoice:
                tax_types = []
                if record.product_id:
                    for tax in record.tax_ids:
                        tax_types.append(tax.code)
                        if tax.code is False:
                            raise ValidationError("This tax doesn't have code")
                        if tax.subtype_code is False:
                            raise ValidationError(
                                "This tax doesn't have a subtype code")
                    set_tax_types = set(tax_types)
                    if len(set_tax_types) < len(tax_types):
                        raise ValidationError(
                            "Only 1 type of each tax is permitted")

    @api.onchange('price_unit', 'quantity', 'tax_ids')
    @api.depends('price_subtotal')
    def _compute_sum_taxable_items(self):
        for record in self:
            record.update({'sum_taxable_items': 0.0})
            taxes = set(record.tax_ids)
            for tax in taxes:
                if tax.amount_type == "percent":
                    record.update({'sum_taxable_items': record.sum_taxable_items + (tax.amount *
                                                                                    record.price_subtotal/100)})
                elif tax.amount_type == "fixed":
                    record.update(
                        {'sum_taxable_items': tax.amount*record.quantity + record.sum_taxable_items})
                elif tax.amount_type == "group":
                    for child_tax in tax.children_tax_ids.flatten_taxes_hierarchy():
                        if child_tax.amount_type == "percent":
                            record.update({'sum_taxable_items': record.sum_taxable_items + (child_tax.amount *
                                                                                            record.sales_total/100)})
                        elif child_tax.amount_type == "fixed":
                            record.update(
                                {'sum_taxable_items': child_tax.amount + record.sum_taxable_items})

    def prepare_taxable_items_json(self):
        self.ensure_one()
        taxable_items = []
        for tax in self.tax_ids:
            if tax.amount_type == "group":
                for child_tax in tax.children_tax_ids.flatten_taxes_hierarchy():
                    taxable_items.append({
                        "taxType": child_tax.code,
                        "amount": float("{:.5f}".format(abs(child_tax.amount*self.quantity))) if child_tax.amount_type == "fixed" else float("{:.5f}".format(abs(tax.amount * self.price_subtotal/100))),
                        "subType": child_tax.subtype_code,
                        "rate": abs(child_tax.amount) if child_tax.amount_type == "percent" else 0
                    })
            else:
                amount = abs(tax.amount*self.quantity) if tax.amount_type == "fixed" else abs(
                    tax.amount * self.price_subtotal/100)
                taxable_items.append({
                    "taxType": tax.code,
                    "amount": float("{:.5f}".format(amount)),
                    "subType": tax.subtype_code,
                    "rate": abs(tax.amount) if tax.amount_type == "percent" else 0
                })

        return taxable_items

    def prepare_unit_value_json(self):
        self.ensure_one()
        unitValue = {}
        currency = self.move_id.currency_id
        currency_EGP = self.env['res.currency'].search([("name", "=", "EGP")])
        unitValue["currencySold"] = currency.name
        if currency.name == "EGP":
            unitValue["amountEGP"] = float("{:.5f}".format(self.price_unit))
        elif currency.name == "USD":
            unitValue["amountEGP"] = float(
                "{:.5f}".format(self.price_unit * currency_EGP.rate))
            unitValue["amountSold"] = float("{:.5f}".format(self.price_unit))
            unitValue["currencyExchangeRate"] = float(
                "{:.5f}".format(currency_EGP.rate))
        else:
            foreign_to_egp = currency_EGP.rate/currency.rate
            unitValue["amountEGP"] = float(
                "{:.5f}".format((self.price_unit * foreign_to_egp)))
            unitValue["amountSold"] = float("{:.5f}".format(self.price_unit))
            unitValue["currencyExchangeRate"] = float(
                "{:.5f}".format(foreign_to_egp))
        return unitValue

    def prepare_invoice_line_json(self):
        self.ensure_one()
        invoice_line = {
            "description": self.product_id.product_tmpl_id.name,
            "itemType": self.item_type,
            "itemCode": self.item_code,
            "unitType": self.unit_type,
            "quantity": self.quantity,
            "internalCode": self.internal_code,
            "salesTotal": float("{:.5f}".format(self.sales_total)),
            "total": float("{:.5f}".format((self.total))),
            "valueDifference": self.value_difference,
            "totalTaxableFees": float("{:.5f}".format((self.total_taxable_fees))),
            "netTotal": float("{:.5f}".format((self.price_subtotal))),
            "itemsDiscount": float("{:.5f}".format((self.items_discount))),
            "unitValue": self.prepare_unit_value_json(),
            "discount": {
                "rate": self.discount,
                "amount": float("{:.5f}".format((self.sales_total - self.price_subtotal)))
            },
            "taxableItems": self.prepare_taxable_items_json()
        }
        return invoice_line

    # @api.onchange('price_unit', 'quantity', 'tax_ids')
    # def print_json(self):
    #     print(self.prepare_invoice_line_json())

    # def write(self,vals):
    #     res = super(YDSInvoiceLine,self).write(vals)
    #    
    #     return res

class YDSInvoice(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'einvoice.mixin','signature.api']

    company_branch_ids = fields.One2many(
        related="company_id.branch_ids")
    def _get_default_branch_id(self):
        branch_ids = self.env.user.company_id.branch_ids
        if branch_ids:
            return branch_ids[0]
        return False
    branch_id = fields.Many2one(comodel_name='issuer.branch', string='Branch' , domain="[('id', 'in', company_branch_ids)]" , default=_get_default_branch_id )
    is_einvoice = fields.Boolean(
        related="journal_id.is_einvoice", readonly=True)
    document_type = fields.Char(string="Document Type",compute='compute_document_type')
    document_type_version = fields.Selection(string='Einvoice Document version', selection=[('0.9', '0.9'), ('1.0', '1.0')], default='1.0')

    # invoice_date = fields.Datetime(string='Invoice/Bill Date', readonly=True, index=True, copy=False,
    #     states={'draft': [('readonly', False)]})
    submit_date = fields.Datetime(index=True, copy=False,
                                  states={'draft': [('readonly', False)]})
    days_expiration = fields.Float(compute="check_expiration", copy=False)
    company_activity_codes = fields.Many2many(
        related="company_id.activity_code_ids")
    move_activity_code = fields.Many2one(
        'account.tax.activity.code', string="Activity Code", domain="[('id', 'in', company_activity_codes)]")
    move_partner_activity_code = fields.Many2one(
        'account.tax.activity.code', readonly=True, compute="_compute_move_partner_activity_code")
    amount_total_egp = fields.Monetary(string='Total_EGP', readonly=True,
                                       compute='_compute_amount_total_egp')

    # # Sum all all InvoiceLine/SalesTotal items
    total_sales_amount = fields.Monetary(
        string="Total Sales Amount", compute="_compute_sales_total", default=0.0)
    # net_amount = fields.Float(
    #     string="Net Amount", compute="_compute_net_amount")
    # # Additional discount amount applied at the level of the overall document, not individual lines.
    # extra_discount_amount = fields.Float(
    #     string="Extra Discount Amount", default=0)  # Not implemented in Odoo
    total_items_discount_amount = fields.Monetary(
        string="Total Items Discount Amount", compute="_compute_total_items_discount_amount")

    total_discount_amount = fields.Monetary(
        string="Total Items Discount Amount", compute="_compute_total_discount_amount")

    file = fields.Binary(
        "File",store=True, copy=False, readonly=True)
    file_name = fields.Char(copy=False, readonly=True)
    # # def _comupte_total(self):
    # #     for record in self:
    # #         for line in record.invoice_line_ids:
    # #             record.total_sales_amount += line.sales_total

    # # def _compute_total_items_discount_amount(self):
    # #     for record in self:
    # #         for line in record.invoice_line_ids:
    # #             record.total_items_discount_amount += line.discount * to

    # # def _compute_net_amount(self):
    # #     for record in self:
    # #         record.net_amount = record.hi

    # ***************************************
    # Optional Fields
    # ***************************************
    # purchase_order_reference string
    # purchase_order_description string
    # sales_order_reference string
    # sales_order_description string
    # proformal_invoice_number string
    # payment FK
    # delivery FK
    # ****************************************

    # ***************************************
    # Fields saved from api response of the submit document
    # ***************************************
    einvoice_submission_id = fields.Char(
        copy=False, string="Submission ID", readonly=False)
    einvoice_document_uuid = fields.Char(
        copy=False, string="Document UUID", readonly=False)
    einvoice_document_long_id = fields.Char(
        copy=False, string="Document longID", readonly=True)
    einvoice_internalId = fields.Char(
        copy=False, string="Document inter", readonly=True)
    einvoice_hashKey = fields.Char(
        copy=False, string="Document Type", readonly=True)
    einvoice_submit_rejected_details_ids = fields.One2many(
        'einvoice.submit.document.rejected.details', 'document_id', string='Rejected Details', copy=False, readonly=True)
    einvoice_document_submission_status = fields.Selection(string='E-invoice Submittion Status', selection=[(
        'accepted', 'Accepted'), ('rejected', 'Rejected'), ('not_submitted', 'Not Submitted'), ('expired', 'Expired')], default='not_submitted', readonly=False, copy=False,)
    # ****************************************

    # ***************************************
    # Fields saved from api response of the get document details
    # ***************************************
    einvoice_status = fields.Selection(copy=False, string='E-Status', selection=[(
        'Valid', 'Valid'), ('Invalid', 'Invalid'), ('Rejected', 'Rejected'), ('Submitted', 'Submitted'), ('Cancelled', 'Cancelled'), ('Cancelling', 'Valid -> Cancel')], readonly=False)
    einvoice_public_url = fields.Char(
        copy=False, string="E-invoice URL", readonly=True)
    einvoice_date = fields.Datetime(
        copy=False, string="E-invoice Date", readonly=True, default=fields.Datetime.now())
    time_to_cancel = fields.Datetime(
        string="Can Cancel Until", copy=False, readonly=True, default=fields.Datetime.now())
    cancellation_date = fields.Datetime(
        copy=False, readonly=True, default=fields.Datetime.now())
    apply_cancellation_date = fields.Datetime(
        copy=False, readonly=True, default=fields.Datetime.now())
    can_cancel = fields.Boolean(compute="compute_can_cancel", copy=False,)
    is_cancelled = fields.Boolean(readonly=True, copy=False,)
    # ****************************************
    # UI Fields
    #invisible on False visible on True
    ui_sync_invoice_visiblity = fields.Boolean(compute="compute_ui_sync_invoice_visiblity", default=False)
    ui_reset_draft_visiblity = fields.Boolean(compute="compute_ui_reset_draft_visiblity", default=False)

    # ****************************************
    last_submittion_time = fields.Datetime( default=fields.Datetime.now(),copy=False)
    def button_draft(self):
        self.write({
            'einvoice_submission_id': False,
            'einvoice_document_uuid': False,
            'einvoice_document_long_id': False,
            'einvoice_hashKey': False,
            'einvoice_submit_rejected_details_ids': [(5, 0, 0)],
            'einvoice_document_submission_status': 'not_submitted',
            'einvoice_status': False,
            'einvoice_public_url': False,
            'einvoice_date': False,
            'time_to_cancel': False,
            'cancellation_date': False,
            'apply_cancellation_date': False,
            'can_cancel': False,
            'is_cancelled': False
        })
        res = super(YDSInvoice, self).button_draft()
        return res
    
    @api.depends('move_type','is_einvoice','einvoice_status')
    def compute_ui_sync_invoice_visiblity(self):
        for record in self:
            record.ui_sync_invoice_visiblity = True
            if record.state not in ['posted'] or record.state in ['cancel']:
                record.ui_sync_invoice_visiblity = False
            elif not record.is_einvoice :
                record.ui_sync_invoice_visiblity = False
            elif record.einvoice_status:
                record.ui_sync_invoice_visiblity = False
            elif record.einvoice_document_submission_status in ['accepted'] and not record.einvoice_status:
                record.ui_sync_invoice_visiblity = False
            elif record.move_type not in ['out_invoice'] and record.move_type not in ['out_refund']:
                record.ui_sync_invoice_visiblity = False

    @api.depends('ui_reset_draft_visiblity','einvoice_document_submission_status','einvoice_status')
    def compute_ui_reset_draft_visiblity(self):
        for record in self:
            record.ui_reset_draft_visiblity = True
            if record.show_reset_to_draft_button == False:
                record.ui_reset_draft_visiblity = False
            elif record.einvoice_status in  ['Valid']:
                record.ui_reset_draft_visiblity = False
            elif record.einvoice_document_submission_status in ['accepted'] and (not record.einvoice_status or record.einvoice_status in ['Submitted']) :
                record.ui_reset_draft_visiblity = False
            
    def compute_document_type(self):
        for record in self:
            record.document_type="i"
            if record.move_type == 'out_refund':
                record.document_type="c"
    @api.onchange('partner_id')
    def _compute_move_partner_activity_code(self):
        for record in self:
            if record.partner_id:
                record.move_partner_activity_code=record.partner_id.partner_activity_code
            else: record.move_partner_activity_code=False

    @api.model
    @api.depends('total_items_discount_amount')
    def _get_tax_totals(self, partner, tax_lines_data, amount_total, amount_untaxed, currency):
        amount_total -= self.total_items_discount_amount
        res = super(YDSInvoice, self)._get_tax_totals(
            partner, tax_lines_data, amount_total, amount_untaxed, currency)
        return res

    # @api.depends('line_ids.amount_currency', 'line_ids.tax_base_amount', 'line_ids.tax_line_id', 'partner_id', 'currency_id', 'amount_total', 'amount_untaxed')
    # def _compute_tax_totals_json(self):
    #     super(YDSInvoice, self)._compute_tax_totals_json()
    #     for move in self:
    #         # print(move.tax_totals_json)
    #         pass

    @api.depends('amount_total')
    def _compute_amount_total_egp(self):
        for record in self:
            currency_EGP = self.env['res.currency'].search(
                [("name", "=", "EGP")])
            if record.currency_id.name == "EGP":
                record.amount_total_egp = record.amount_total
            if record.currency_id.name == "USD":
                record.amount_total_egp = record.amount_total * currency_EGP.rate
            else:
                record.amount_total_egp = record.amount_total * \
                    (currency_EGP.rate/record.currency_id.rate)

    @api.depends('invoice_line_ids.sales_total')
    def _compute_sales_total(self):
        for record in self:
            move_currency = record.currency_id.name
            move_currency_rate = record.currency_id.rate
            calc_total_sales_amount = 0.0
            for line in record.invoice_line_ids:
                if line.currency_id.name == move_currency:
                    calc_total_sales_amount += line.sales_total
                elif line.currency_id.name == "USD":
                    calc_total_sales_amount += (line.sales_total *
                                                move_currency_rate)
                else:
                    calc_total_sales_amount += (line.sales_total *
                                                (move_currency_rate/line.currency_id.rate))
            record.total_sales_amount = float(
                "{:.5f}".format(calc_total_sales_amount))

    @api.onchange('invoice_line_ids')
    def _compute_total_discount_amount(self):
        for record in self:
            total_discount_amount = 0.0
            for line in record.invoice_line_ids:
                total_discount_amount += line.sales_total - line.price_subtotal
            record.total_discount_amount = float(
                "{:.5f}".format(total_discount_amount))

    @api.onchange('invoice_line_ids.items_discount')
    def _compute_total_items_discount_amount(self):
        for record in self:
            total_items_discount_amount = 0.0
            for line in record.invoice_line_ids:
                total_items_discount_amount += line.items_discount
            record.total_items_discount_amount = float(
                "{:.5f}".format(total_items_discount_amount))

    def get_tax_totals(self):
        tax_totals = {}
        for record in self:
            for line in record.invoice_line_ids:
                tax_dic = line.prepare_taxable_items_json()
                for item in tax_dic:
                    if item["taxType"] not in tax_totals:
                        tax_totals[item["taxType"]] = 0
                    tax_totals[item["taxType"]] += item["amount"]
        return tax_totals

    def prepare_tax_totals(self):
        tax_totals = []
        for record in self:
            tax_disc = record.get_tax_totals()
            for key, value in tax_disc.items():
                tax_totals.append({
                    "taxType": key,
                    "amount": float("{:.5f}".format(value))
                })
        return tax_totals

    def prepare_receiver_json(self):
        self.ensure_one()
        partner = self.partner_id
        if partner.company_type=='person':
            if partner.parent_id:
                master_partner = partner.parent_id
                if master_partner.company_type=='company':
                    partner= master_partner
        #print(partner.name)
        partner_json = partner.prepare_receiver_json()
        address_json = partner.prepare_address_json()
        if partner:
            if partner_json["type"] != 'P':
                partner_json["id"] = partner.vat
                partner_json["name"] = partner.name
                partner_json["address"] = address_json
            elif partner_json["type"] == "P" and self.amount_total_egp >= 50000:
                partner_json["id"] = partner.vat
                partner_json["name"] = partner.name
                partner_json["address"] = address_json
            elif partner_json["type"] == "P" and self.amount_total_egp < 50000:
                if partner.vat:
                    partner_json["id"] = partner.vat
                if partner.name:
                    partner_json["name"] = partner.name
                    # if address_json:
                    #     partner_json["address"] = address_json
                
            return partner_json
        else:
            raise ValidationError("No partner is set")

    def prepare_invoice_lines_json(self):
        invoice_lines_json = []
        for record in self:
            for line in record.invoice_line_ids:
                invoice_lines_json.append(line.prepare_invoice_line_json())
        return invoice_lines_json

    def prepare_document_json(self):
        for record in self:
            document = {
                "issuer": record.company_id.prepare_issuer_json(record.branch_id),
                "receiver": record.prepare_receiver_json(),
                "documentType": record.document_type,
                "documentTypeVersion": record.document_type_version,
                "dateTimeIssued": str(record.invoice_date)+'T'+'00:00:00Z',
                "taxpayerActivityCode": record.move_partner_activity_code.code,
                "internalID": record.name,
                "invoiceLines": record.prepare_invoice_lines_json(),
                "totalSalesAmount": float("{:.5f}".format((record.total_sales_amount))),
                "totalDiscountAmount": float("{:.5f}".format((record.total_discount_amount))),
                "netAmount": float("{:.5f}".format((record.amount_untaxed))),
                "totalAmount": float("{:.5f}".format((record.amount_total))),
                "extraDiscountAmount": 0,
                "totalItemsDiscountAmount": float("{:.5f}".format((record.total_items_discount_amount))),
                "taxTotals": record.prepare_tax_totals()
            }
            #print("DOCUMENT TYPE")
            #print(record.document_type)
            if record.document_type_version == '1.0':
                serializedString = record.canoncalize_document(document)
                signature=record.generate_signature(serializedString)
                document['signatures'] = [{
                    "signatureType": "I",
                    "value":signature
                }]
            return document

    def nested_dict_pairs_iterator(self, d):
        for key, value in d.items():
            # Check if value is of dict type
            if isinstance(value, list):
                for val in value:
                    if isinstance(val, dict):
                        # If value is dict then iterate over all its values
                        for pair in self.nested_dict_pairs_iterator(val):
                            yield (key, *pair)
                    else:
                        # If value is not dict type then yield the value
                        yield (key, val)
            else:
                if isinstance(value, dict):
                    # If value is dict then iterate over all its values
                    for pair in self.nested_dict_pairs_iterator(value):
                        yield (key, *pair)
                else:
                    # If value is not dict type then yield the value
                    yield (key, value)

    def validate_document(self, document):
        for record in self:
            invalid_items = []
            error_message = "Missing: "
            for pair in record.nested_dict_pairs_iterator(document):

                if pair[-1] is False:
                    invalid_items.append(pair)
            for idx, invalid_item in enumerate(invalid_items):
                error_message += "\n " + str(idx+1)+"- "
                for idx2, field in enumerate(invalid_item):
                    if idx2 == len(invalid_item)-1:
                        break
                    error_message += str(field)+" "
            if invalid_items:
                raise ValidationError(
                    "Invoice ID: "+record.name+"\n"+error_message)

    def submit_document(self):
        if self.company_id.einvoice_login_status == 'logged_out':
            self.company_id.login_request()

        documents = []
        for record in self:
            
            if record.state == 'posted' and record.einvoice_status != 'Valid' and record.is_einvoice:
                document = record.prepare_document_json()
                
                record.validate_document(document)
                documents.append(document)
        if documents:
            _logger.info('\nYDS: Calling submit document api')
            items = einvoice_submit_document(company=self.company_id, documents=documents,
                                                  token=self.company_id.token, url=self.company_id.api_base_url)
            
            print("items")
            print(items)
            if items:
                rejected_documents = items.get('rejectedDocuments')
                accepted_documents = items.get('acceptedDocuments')
                for record in self:
                    if rejected_documents:
                        for i, document in enumerate(rejected_documents):
                            if record.name == document['internalId']:
                                details = document.get('error').get('details')
                                submitted_details = []
                                for detail in details:
                                    code = detail.get('code')
                                    message = detail.get('message')
                                    target = detail.get('target')
                                    property_path = detail.get('propertyPath')
                                    submitted_details.append(
                                        (0, 0, {'code': code, 'message': message, 'target': target, 'property_path': property_path}))
                                record.update({
                                    'einvoice_document_submission_status': 'rejected',
                                    'einvoice_submission_id': items.get('submissionId'),
                                    'einvoice_submit_rejected_details_ids': submitted_details,
    
                                })
                                _logger.info('\nYDS:SUBMITTION Writing in Invoice %s fields: \n\
                                 einvoice_submission_id = %s \n\
                                 einvoice_document_submission_status = %s   ',
                                 record.name,record.einvoice_submission_id,record.einvoice_document_submission_status)
                    if accepted_documents:
                        for i, document in enumerate(accepted_documents):
                            if record.name == document['internalId']:
                                record.update({
                                    'einvoice_submission_id': items.get('submissionId'),
                                    'einvoice_document_uuid': items.get('acceptedDocuments')[i].get('uuid'),
                                    'einvoice_document_long_id': items.get('acceptedDocuments')[i].get('longId'),
                                    'einvoice_internalId': items.get('acceptedDocuments')[i].get('internalId'),
                                    'einvoice_document_submission_status': 'accepted',
                                    'einvoice_hashKey': items.get('acceptedDocuments')[i].get('hashKey'),
                                    'einvoice_submit_rejected_details_ids': [(5, 0, 0)],
                                })
                                _logger.info('\nYDS:SUBMITTION Writing in Invoice %s fields: \n\
                                einvoice_submission_id =%s \n\
                                 einvoice_document_uuid = %s \n\
                                 einvoice_internalId = %s \n\
                                 einvoice_document_submission_status = %s   ',
                                 record.name,record.einvoice_submission_id,record.einvoice_document_uuid,record.einvoice_internalId,record.einvoice_document_submission_status)

    def get_document_details(self):
        if self.company_id.einvoice_login_status == 'logged_out':
            self.company_id.login_request()
        for record in self:
            if record.einvoice_document_submission_status == 'accepted':
                details = record.einvoice_get_document_details(company=record.company_id, uuid=record.einvoice_document_uuid,
                                                               token=record.company_id.token, url=record.company_id.api_base_url)
                if details != 404:
                    record.update({
                        'einvoice_status': details.get('status'),
                        'einvoice_public_url': details.get('publicUrl'),
                        'einvoice_date': datetime.strptime((details.get('dateTimeRecevied')).split(".")[0], '%Y-%m-%dT%H:%M:%S'),
                        'time_to_cancel': datetime.strptime((details.get('canbeCancelledUntil')).split(".")[0], '%Y-%m-%dT%H:%M:%S'),
                    })
                    _logger.info('\nYDS:DETAILS Writing in Invoice %s fields: \n\
                                 einvoice_status = %s \n\
                                 einvoice_public_url = %s \n\
                                 einvoice_date = %s   ',
                                 record.name,record.einvoice_status,record.einvoice_public_url,record.einvoice_date)

                    if record.is_cancelled == True and record.einvoice_status != 'Cancelled':
                        record.update({
                            'einvoice_status': 'Cancelling'})
                        _logger.info('\nYDS:DETAILS Writing in Invoice %s fields: \n\
                             einvoice_status = %s \n',
                             record.name,record.einvoice_status)
                    # if record.einvoice_status == 'Cancelling':
                    #     record.update({

                    #     })
                    if details.get('cancelRequestDate') != None:
                        record.update({'cancellation_date': datetime.strptime((details.get('cancelRequestDate')).split(".")[0], '%Y-%m-%dT%H:%M:%S')
                                       })
                    if details.get('cancelRequestDelayedDate') != None:
                        record.update({'apply_cancellation_date': datetime.strptime((details.get('cancelRequestDelayedDate')).split(".")[0], '%Y-%m-%dT%H:%M:%S')
                                       })
                    _logger.info('\nYDS: Details For Invoice: %s with document ID: %s and status: %s',record.name,record.einvoice_document_uuid,details.get('status'))
                    record.download_document_invoice()
                if len(self) == 1:
                    if details != 404:
                        if details.get('status') == 'Invalid':
                            validation_steps = details.get(
                                'validationResults').get('validationSteps')
                            return {
                                'type': 'ir.actions.act_window',
                                'name': _('Why Document is Invalid:'),
                                'res_model': 'yds.einvoice.invalid.details.wizard',
                                'target': 'new',
                                'view_id': self.env.ref('e-invoice.view_show_errors_wizard_view_form').id,
                                'view_mode': 'form',
                                'context': {
                                    'einvoice_document_uuid': self.einvoice_document_uuid,
                                    'einvoice_status': self.einvoice_status,
                                    'validation_steps': validation_steps,
                                }
                            }

    def sync_einvoice(self):
        for record in self:
            current_time = datetime.now()
            diff = (current_time - record.last_submittion_time).total_seconds()
            _logger.info('\nYDS:SYNC Last Submittion date for record %s is %s \n',record.name,record.last_submittion_time)
            if diff < 30.0:
                _logger.info('\nYDS:SYNC Many requests returning from sync_einvoice\n')
                return
            record.last_submittion_time = datetime.now()

            if record.move_type not in ['out_invoice','out_refund']:
                raise ValidationError("One or more of the the selected records are not Credit Note or Invoices")

        self.update({'einvoice_submit_rejected_details_ids': [(5, 0, 0)]})
        self.submit_document()
        is_sleep = False
        for record in self:
            if record.einvoice_document_submission_status == 'accepted':
                if is_sleep == False:
                    sleep(5)
                    is_sleep = True
        self.get_document_details()
        #
        # for record in self:

    @api.onchange('invoice_date')
    def check_expiration(self):
        for record in self:
            if record.invoice_date:
                expiration_date = record.invoice_date+timedelta(days=7)
                days = (expiration_date-fields.Date.today()).days
                if days < 0.0:
                    days = 0
                    if record.einvoice_status == 'Invalid' or record.einvoice_document_submission_status == 'not_submitted':
                        record.einvoice_document_submission_status = 'expired'
                        
                elif days >= 0 and record.einvoice_document_submission_status != 'accepted':
                    record.einvoice_document_submission_status = 'not_submitted'
                record.days_expiration = days
                return
            record.days_expiration = 7

    @api.depends('time_to_cancel','einvoice_status')
    def compute_can_cancel(self):
        for record in self:
            record.can_cancel = False
            if record.time_to_cancel and record.einvoice_status:
                if record.time_to_cancel > fields.Datetime.now() and (record.einvoice_status == 'Valid' or record.einvoice_status == 'Submitted'):
                    record.can_cancel = True
                else:
                    record.can_cancel = False

    def cancel_einvoice(self):
        if self.company_id.einvoice_login_status == 'logged_out':
            self.company_id.login_request()

        if self.ensure_one():
            return {
                'type': 'ir.actions.act_window',
                'name': _('State Cancel Reason:'),
                'res_model': 'yds.einvoice.cancel.wizard',
                'target': 'new',
                'view_id': self.env.ref('e-invoice.view_cancel_einvoice_wizard_view_form').id,
                'view_mode': 'form',
                'context': {
                    'einvoice_document_uuid': self.einvoice_document_uuid,
                    'move_id': self.id,
                    'token': self.company_id.token,
                    'url': self.company_id.api_base_url
                }
            }

        for record in self:
            response = record.einvoice_cancel_document(uuid=record.einvoice_document_uuid,
                                                       token=record.company_id.token, url=record.company_id.api_base_url, reason="some reason")
            if response == "ok":
                record.is_cancelled = True
                sleep(1)
                record.get_document_details()
            elif response == "no":
                record.is_cancelled = False

    def download_document_invoice(self):
        for record in self:
            if record.einvoice_status == 'Valid' or record.einvoice_status == 'Rejected ' or record.einvoice_status == 'Cancelled' or record.einvoice_status == 'Cancelling':
                response = record.einvoice_download_document(
                    uuid=record.einvoice_document_uuid, token=record.company_id.token, url=record.company_id.api_base_url)
                try:
                    
                    record.update({
                        'file': base64.b64encode(response),
                        'file_name': str(record.name)+".pdf"
                    })
                    _logger.info('\nYDS:DOWNLOAD Writing in Invoice %s fields: \n\
                                 file_name = %s \n',
                                 record.name,record.file_name)
                    return
                except: 
                    
                    record.update({
                    'file': "",
                    'file_name': str(record.name)+".pdf"
                    })
                    _logger.info('\nYDS:DOWNLOAD failed to download  Invoice %s ',
                                 record.name)
                    return

                                       
    def canoncalize_document(self,document):
        tags = "\""
        for record in self:
            if isinstance(document,float) or isinstance(document,str) or isinstance(document,int):
                return str(tags+str(document)+tags)
            
            serializedString = ""
           
            for element in document:
                value = document.get(element)
                if not isinstance(value,list):
                    
                    serializedString += tags+str(element).upper()+tags
                    serializedString += str(self.canoncalize_document(value))

                if isinstance(value,list):
                    serializedString += tags+str(element).upper()+tags 
                    for item in value:
                        serializedString += tags+str(element).upper()+tags 
                        serializedString += self.canoncalize_document(item)
            
            return serializedString
            
    def generate_signature(self,serialized_string):
        for record in self:
            company = record.company_id
            company.test_signature_connection()
            if company.sig_connect == True:
                signature=record.generate_signature_api(company.signature_ip,company.signature_port,serialized_string,company.token_subject_name)
                return signature
            else:
                raise ValidationError("Can't reach Signature App")

