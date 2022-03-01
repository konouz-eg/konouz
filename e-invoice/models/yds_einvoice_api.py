import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging
import requests
from datetime import datetime
# from .issuer import Issuer

_logger = logging.getLogger(__name__)
class EinvoiceMixin(models.AbstractModel):
    _name = 'einvoice.mixin'

    def einvoice_cron_check_loggin(self):
        companies = self.env['res.company'].search([])
        for company in companies:
            if company.einvoice_login_status != 'logged_out':
                url = company.api_base_url+'/api/v1/documenttypes'
                header = {'Content-Type': 'application/json',
                        'Authorization': company.token}
                response = requests.get(url, headers=header)
                if response.status_code == 401 or response.status_code == 403:
                    company.update({'einvoice_login_status': 'logged_out'})

    def einvoice_loggin(self, company):
        # if isinstance(company_id, Issuer):
        url = company.id_srv_base_url+'/connect/token'
        data = {'grant_type': 'client_credentials',
                'client_id': company.client_id,
                'client_secret': company.client_secret,
                'scope': 'InvoicingAPI'}
        header = {'Content-Type': 'application/x-www-form-urlencoded'}
        #response= requests.get(url1,headers=header)
        response = requests.post(url, data=data, headers=header)
        
        if response.status_code == 200:
            company.update({'token': response.json().get('token_type') + " " + \
                response.json().get('access_token')})
            company.update({'einvoice_login_status': 'logged_in'})
        else:
            company.update({'einvoice_login_status': 'logged_out'})

    # this function has been move to utils.py file
    # def einvoice_submit_document(self,company,documents, token, url):
        
    #     print("IN SUBMIT DOCUMENTS")
    #     url = url+'/api/v1/documentsubmissions'
    #     data = {'documents': documents,}
    #     header = {'Content-Type': 'application/json',
    #                   'Authorization': token}
    #     json_object = json.dumps(data, ensure_ascii = False).encode('utf-8')
    #     print(json_object)
    #     response = requests.post(url, data=json_object, headers=header)
    #     _logger.info(' ****************************************************\n Submit Document  request with date  %s **************************************************************\n', str(datetime.now()))
    #     for document in documents:
    #         _logger.info('\nDocument InternalID: %s \n',document['internalID'])
    #     if response.status_code == 422:
    #         raise ValidationError(response.json().get('error'))
    #     if response.status_code == 202:
    #         return response.json()
    #     else:
    #         _logger.error('Cant Submit Document request with date  %s got response code: %s: %s\n',str(datetime.now()),response.status_code)
    #         raise ValidationError("ERROR occurred while submitting document with code:%s ",response.status_code)

    def einvoice_get_document_details(self,company,uuid, token, url):
        url = url+'/api/v1/documents/'+uuid+'/details'
        header = {'Accept':'application/json',
        'Content-type':'application/json',
        'Authorization': token}
        response = requests.get(url, headers=header)
        if response.status_code==200:
            return response.json()
        if response.status_code==504:
            raise ValidationError("Document submitted but timmed out for Status")
        else: return 404

    def einvoice_cancel_document(self,uuid, token, url ,reason):
        url = url+'/api/v1.0/documents/state/'+uuid+'/state'
        data = {'status':"cancelled",
        'reason':reason}
        header = { 'Content-type':'application/json',
        'Accept':'*/*',
        'Authorization': token}
        json_object = json.dumps(data, indent = 4, ensure_ascii = False).encode('utf-8')
       
        response = requests.put(url,data=json_object, headers=header)
        
        if response.status_code==200:
            return "ok"
        if response.status_code==504:
            raise ValidationError("Document submitted but timmed out for Status")
        if response.status_code==400:
            raise ValidationError(response.json().get('error').get('details')[0].get('message'))
        return "no"
    

    def einvoice_decline_cancel_document(self,uuid, token, url):
        url = url+'/api/v1.0/documents/state/'+uuid+'/decline/cancelation'
        header = {'Accept':'application/json',
        'Content-type':'application/json',
        'Authorization': token}
        response = requests.put(url, headers=header)
        if response.status_code==200:
            return "ok"
        if response.status_code==504:
            raise ValidationError("Document submitted but timmed out for Status")
        return "no"

    def einvoice_download_document(self,uuid,token,url):
        url = url+'/api/v1/documents/'+uuid+'/pdf'
        header = {
        'Authorization': token}
        response = requests.get(url, headers=header, allow_redirects=True)

        if response.status_code==200:
            return response.content
            
        if response.status_code==504:
            raise ValidationError("Document submitted but timmed out for Status")
        return response.json()