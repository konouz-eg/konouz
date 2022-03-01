  
import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging
import requests
from datetime import datetime

_logger = logging.getLogger(__name__)
internal_ids = []
last_submittion_time = datetime.now()


def common_member(a, b):
    a_set = set(a)
    b_set = set(b)
    if len(a_set.intersection(b_set)) > 0:
        return(True) 
    return(False) 

def einvoice_loggin(company):
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

def einvoice_submit_document(company,documents, token, url):
    global internal_ids
    global last_submittion_time
    #print("IN SUBMIT DOCUMENTS API")
    current_time = datetime.now()
    print("current_time: ", current_time)
    print("Last submittion time: ",last_submittion_time)
    print(internal_ids)
    diff = (datetime.now() - last_submittion_time).total_seconds()
    my_document_ids= []
    for document in documents:
        my_document_ids.append(document['internalID'])
    if diff < 30.0 and common_member(internal_ids,my_document_ids):
        _logger.info('\nYDS: Many requests returning from einvoice_submit_document in utils within %s',diff)
        return None
    url = url+'/api/v1/documentsubmissions'
    data = {'documents': documents,}
    header = {'Content-Type': 'application/json',
                  'Authorization': token}
                  
    json_object = json.dumps(data, ensure_ascii = False).encode('utf-8')
    #print(json_object)
    response = requests.post(url, data=json_object, headers=header)

    
    _logger.info('YDS:UTILS ****************************************************\n Submit Documents  request with date  %s **************************************************************\n', str(datetime.now()))
    internal_ids = []
    for document in documents:
        internal_ids.append(document['internalID'])
        _logger.info('\nYDS:UTILS Document InternalID: %s \n',document['internalID'])
    #print("STATUS CODE: ",response.status_code)
    if response.status_code == 422:
        raise ValidationError(response.json().get('error'))
    if response.status_code == 202 or response.status_code == 200:
        print("HERE")
        print(response._content)
        print(response.headers)
        last_submittion_time = datetime.now()
        return response.json()
    else:
        _logger.error('YDS: Cant Submit Document request with date  %s got response code: %s\n',str(datetime.now()),response.status_code)
        raise ValidationError("ERROR occurred while submitting document with code: "+str(response.status_code))


def einvoice_get_document_details(company,uuid, token, url):
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