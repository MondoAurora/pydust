from dust.httpservices import DustResultType

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
