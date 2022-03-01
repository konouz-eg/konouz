
from odoo import models, fields, api

class YDSEinvoiceSubmitDocumentRejectedDetails(models.Model):
    _name ="einvoice.submit.document.rejected.details"
    document_id = fields.Many2one('account.move', string='Journal Entry',
        index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
        check_company=True,
        help="The move of this entry line.")
    code = fields.Char()
    message = fields.Char()
    target = fields.Char()
    property_path = fields.Char()