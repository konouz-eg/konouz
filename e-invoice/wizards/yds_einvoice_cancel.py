from time import sleep
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class YdsCancel(models.TransientModel):
    _name = 'yds.einvoice.cancel.wizard'
    _inherit = 'einvoice.mixin'
    reason = fields.Char(string="Reason",required=True)

    def cancel_einvoice(self):
        uuid = self._context.get('einvoice_document_uuid')
        move_id = self._context.get('move_id')
        token = self._context.get('token')
        url = self._context.get('url')

        move = self.env['account.move'].browse([move_id])[0]
        response = self.einvoice_cancel_document(uuid=uuid,token=token,url=url,reason=self.reason)
        if response=="ok":

            sleep(1)
            move.get_document_details()
            move.update({
                'is_cancelled':True,
                'einvoice_status':'Cancelling'
            })
        elif response=="no":
            move.update({
                'is_cancelled':True
            })


    
    

