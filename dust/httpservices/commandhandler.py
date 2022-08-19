from dust import logger
from dust.httpservices import SVCINFO_USER, SVCINFO_AUTHINFO, SVCINFO_CLIENTIP, SVCINFO_TIMESTAMP, SVCLOG_RESPONSE, SVCRESP_STATUS
from dust.httpservices.actioncontroller import ActionController

from datetime import datetime
import traceback
import json

class CommandHandler():
    def __init__(self, server, request_wrapper, *service_names):
        self.server = server
        self.request_wrapper = request_wrapper
        self.action_ctrl = ActionController(*service_names)

    def send_json_response(self, esp_data, http_status):
        pass

    def get_session_user(self, request):
        pass

    def handle(self, target, request, response):
        request = self.request_wrapper(request)
        cmd = target

        if cmd.startswith("/"):
            cmd = cmd[1:]

        param = None
        param_idx = cmd.find("/")

        if param_idx != -1:
            param = cmd[param_idx+1:]
            cmd = cmd[0:param_idx]

        logger().debug("Server cmd: {}, param: {}".format(cmd, param))

        success = False
        resp_data = {}
        http_status = 204

        try:
            if cmd == "getSessionUser":
                resp_data = self.get_session_user(request)

            elif cmd == "api":
                input_data = request.get_json()
                if input_data == None:
                    input_data = {}

                input_data.update(request.get_query_params())

                self.log(input_data, "Input data is:")

                auth_data = self.get_session_user(request)

                input_data[SVCINFO_USER] = auth_data.get("uid")
                input_data[SVCINFO_AUTHINFO] = auth_data
                input_data[SVCINFO_CLIENTIP] = request.remote_addr()
                input_data[SVCINFO_TIMESTAMP] = datetime.now()

                success = self.action_ctrl.relay_action(input_data, request, resp_data)
                if success:
                    http_status = 200

                pass 
            elif cmd == "ping":
                pass 

        except:
            traceback.print_exc()

        if resp_data:
            response[SVCRESP_STATUS] = success
            response[SVCLOG_RESPONSE] = resp_data


    def log(self, json_data, msg=None):
        if msg:
            logger().debug(msg)
        logger().debug(json.dumps(json_data, indent=4))