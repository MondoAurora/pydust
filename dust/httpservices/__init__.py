from enum import Enum

__all__ = ["actioncontroller","servicebase","commandhandler"]

SVCINFO_USER = "userId"
SVCINFO_AUTHINFO = "AuthInfo"
SVCINFO_CLIENTIP = "clientIp"
SVCINFO_TIMESTAMP = "timestamp"
SVCINFO_MODULE = "module"

SVCPARAM_COMMAND = "command"
SVCPARAM_TARGET = "target"
SVCPARAM_CONTENT = "Content"
SVCPARAM_EXTRAPARAMS = "ExtraParams"

SVCRESP_STATUS = "status"
SVCRESP_ERRORMSG = "errorMsg"
SVCLOG_EXECLOG = "ExecLog"

SVCLOG_REQUEST = "Request"
SVCLOG_RESPONSE = "Response"
    
SVCREJECT_STATUS = "httpStatus"
SVCREJECT_CHECK = "rejectCheck"
SVCREJECT_MESSAGE = "rejectMessage"


class DustResultType(Enum):
    NOTIMPLEMENTED = 1
    REJECT = 2
    ACCEPT_PASS = 3
    ACCEPT = 4
    ACCEPT_READ = 5
    READ = 6

    def is_readon(self):
        return self.value == DustResultType.READ or self.value == DustResultType.ACCEPT_READ

    def is_reject(self):
        return self.value == DustResultType.NOTIMPLEMENTED or self.value == DustResultType.REJECT

class RequestWrapper():
    def __init__(self, request):
        self.request = request

    def get_method(self):
        pass

    def get_query_params(self):
        pass 

    def get_json(self):
        pass

    def get_path(self):
        pass

    def remote_addr(self):
        pass