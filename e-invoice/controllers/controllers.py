# -*- coding: utf-8 -*-
import os
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import Response, request
from reportlab.pdfgen import canvas
import requests
import base64
class E_invoice_controller(http.Controller):

  pass