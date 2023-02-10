from dust.httpservices import DustResultType
import gzip
import json
import base64

import traceback

_services = {}

class ServiceBase():
	def __init__(self, module):
		self.module = module
		_services[module] = self

	@staticmethod
	def get_service(name):
		return _services.get(name)

	def do_process(self, params, request, response, immediate=True):
		if immediate:
			return DustResultType.ACCEPT
		else:
			return DustResultType.NOTIMPLEMENTED

	def get_modulename(self):
		return self.module 

	def compress(self, filename, json_data):
		encoded_data = None
		try:
			with gzip.open(filename, 'w') as fout:
				fout.write(json.dumps(json_data).encode('utf-8'))  

			with gzip.open(filename, 'r') as fin:
				encoded_data = base64.b64encode(fin.read()).decode()
		except:
			traceback.print_exc()

		return encoded_data
