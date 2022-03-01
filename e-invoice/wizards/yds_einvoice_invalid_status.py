from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class YDSInvalidDetails(models.TransientModel):
    _name = 'yds.einvoice.invalid.details.wizard'

    def compute_einvoice_document_uuid(self):
        return self._context.get('einvoice_document_uuid')
    einvoice_document_uuid=fields.Char(string="Document UUID",default=compute_einvoice_document_uuid,readonly=True)
    
    def compute_einvoice_status(self):
        return self._context.get('einvoice_status')
    einvoice_status= fields.Selection(string='E-Status',default=compute_einvoice_status, selection=[(
        'Valid', 'Valid'), ('Invalid', 'Invalid'), ('Rejected', 'Rejected'), ('Submitted', 'Submitted'), ('Cancelled', 'Cancelled')],readonly=True)
    
    def compute_details(self):
        validation_steps = self._context.get('validation_steps')
        x = ""
        for step in validation_steps:
            if step.get('status') == "Invalid":
                error_items=""
                for inner_error in step.get('error').get('innerError'):
                    error_items+= f"<td style='padding:10px;'> {inner_error.get('propertyName')} </td>"\
                        +f"<td style='padding:10px;'> {inner_error.get('propertyPath')} </td>"\
                        +f"<td style='padding:10px;'> {inner_error.get('error')} </td>"\
                        +f"<td style='padding:10px; text-align: right;'> {inner_error.get('errorAr')} </td>"\
                
                    x += "<tr>"\
                        +f"<td style='padding:10px;'> {step.get('error').get('error')} </td>"\
                        +f"<td style='padding:10px;  text-align: right;'> {step.get('error').get('errorAr')} </td>"\
                        +error_items\
                    +"</tr>"
                    error_items=""

               
                            
                return ("<table border="'2px'" bordercolor="'#000000'">"\
                +"<thead>"
                            +"<tr style='padding:10px;'>"\
                                +" <th ><h4 align="'center'">Error</h4></th>"\
                                +"<th><h4 align="'center'">ErrorAr</h4></th>"\
                                +"<th colspan='4'><h4 align="'center'">InnerError</h4></th>"\
                            +"</tr>"\
                            +"<tr style='padding:10px;'>"\
                                     +"<th colspan='2'></th>"\
                                    +"<th style='padding:10px;'><h4 align="'center'">propertyName</h4></th>"\
                                    +"<th><h4 align="'center'">propertyPath</h4></th>"\
                                    +"<th><h4 align="'center'">error</h4></th>"\
                                    +"<th><h4 align="'center'">errorAr</h4></th>"\
                            +"</tr>"\
                +"</thead>"
                            +x+"</table>")
    details = fields.Html(default=compute_details,readonly=1)
    
    

