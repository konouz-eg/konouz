import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import requests
# from .issuer import Issuer


class SignatureApis(models.AbstractModel):
    _name = 'signature.api'

    def signature_test_connection(self,ip,port,subject_name):
        url = "http://"+ip+":"+port+"/generateSignature"
        data = {"data": "test",
                "name": subject_name
                }
        header = {'Content-Type': 'application/json'}
        json_object = json.dumps(data, indent = 4, ensure_ascii = False).encode('utf-8')
        response = requests.post(url, data=json_object, headers=header,timeout=60)
        #print(response.status_code)
        return response.status_code

    def generate_signature_api(self,ip,port,sig_text,subject_name):
        url = "http://"+ip+":"+port+"/generateSignature"
        data = {"data": sig_text,
                "name": subject_name
                }
        header = {'Content-Type': 'application/json'}
        json_object = json.dumps(data, indent = 4, ensure_ascii = False).encode('utf-8')
        try:
            response = requests.post(url, data=json_object, headers=header,timeout=15)
            if response.status_code==204:
                raise ValidationError("Subject name didn't match the certificate")
            return str(response.json())
        except:
            return 500