# -*- coding: utf-8 -*-

import phantom.app as phantom
from phantom.base_connector import BaseConnector
from phantom.action_result import ActionResult

# Usage of the consts file is recommended
# from mark2server_consts import *
import requests
import json
import tempfile
import os


class RetVal(tuple):
    def __new__(cls, val1, val2=None):
        return tuple.__new__(RetVal, (val1, val2))


class Mark2ServerConnector(BaseConnector):
    def __init__(self):
        # Call the BaseConnectors init first
        super(Mark2ServerConnector, self).__init__()

        self._state = None
        self._url = None
        self._cert = None
        self._verify = False
        self._headers = {}

    def _process_response(self, r, action_result):
        # store the r_text in debug data, it will get dumped in the
        # logs if the action fails
        if hasattr(action_result, 'add_debug_data'):
            action_result.add_debug_data({'r_status_code': r.status_code})
            action_result.add_debug_data({'r_text': r.text})
            action_result.add_debug_data({'r_headers': r.headers})

        try:
            resp_json = r.json()
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR,
                          "Unable to parse JSON response. Error: {0}"
                          .format(str(e))), None)

        if 200 <= r.status_code < 399:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        message = "Error from server. " + \
                  "Status Code: {0} Data from server: {1}" \
                  .format(r.status_code,
                          r.text.replace('{', '{{').replace('}', '}}'))
        return RetVal(action_result.set_status(phantom.APP_ERROR,
                      message), None)

    def _make_rest_call(self, endpoint, action_result, headers=None,
                        params=None, data=None, method="get", verify=False):
        try:
            request_func = getattr(requests, method)
        except AttributeError:
            return RetVal(action_result.set_status(phantom.APP_ERROR,
                          "Invalid method: {0}".format(method)), None)
        try:
            r = request_func(self._url, data=data, headers=headers,
                             verify=verify, params=params)
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR,
                          "Error Connecting to server. Details: {0}"
                          .format(str(e))), None)
        return self._process_response(r, action_result)

    def _handle_test_connectivity(self, param):
        # Add an action result object to self (BaseConnector) to
        # represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # NOTE: test connectivity does _NOT_ take any parameters
        # i.e. the param dictionary passed to this handler will be empty.
        # Also typically it does not add any data into an action_result either.
        # The status and progress messages are more important.
        data = {
          'name': 'dummy',
          'target': { 'addr': '0.0.0.0', 'subnet': '0', 'pc_name': 'dummy' },
          'period': 1,
          'net_ctrl': [ {
            'name': 'dummy',
            'net': { 'addr': '0.0.0.0', 'subnet': '0', 'port': '0' }
          } ]
        }

        self.save_progress("Connecting to the Mark II Server")
        ret_val, response = \
            self._make_rest_call(self._url, action_result,
                                 headers=self._headers, data=json.dumps(data),
                                 method='post', verify=self._verify)

        if (phantom.is_fail(ret_val)):
            # the call to the 3rd party device or service failed,
            # action result should contain all the error details
            # so just return from here
            self.save_progress("Test Connectivity Failed.")
            return action_result.get_status()

        self.save_progress("Test Connectivity Passed")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_isolate_device(self, param):
        # Implement the handler here
        # use self.save_progress(...) to send progress messages back
        # to the platform
        self.save_progress("In action handler for: {0}"
                           .format(self.get_action_identifier()))

        # Add an action result object to self (BaseConnector) to
        # represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        data = {
            'name': 'isolate',
            'target': { 'addr': param['ipaddr'], 'subnet': '32' },
            'net_ctrl': [ {
                    'name': 'all',
                    'net': { 'addr': '0.0.0.0', 'subnet': '0', 'port': '0' }
            } ]
        }
        if param.get('period', 0) > 0:
            data['period'] = param['period']

        ret_val, response = \
            self._make_rest_call(self._url, action_result,
                                 headers=self._headers, data=json.dumps(data),
                                 method='post', verify=self._verify)

        if (phantom.is_fail(ret_val)):
            # the call to the 3rd party device or service failed,
            # action result should contain all the error details
            # so just return from here
            return action_result.get_status()

        # Add the response into the data section
        action_result.add_data(response)

        # Add a dictionary that is made up of the most important
        # values from data into the summary
        summary = action_result.update_summary({})
        summary['isolated'] = param['ipaddr']

        # Return success, no need to set the message, only the status
        # BaseConnector will create a textual message based off of the
        # summary dictionary
        return action_result.set_status(phantom.APP_SUCCESS)

    def handle_action(self, param):
        ret_val = phantom.APP_SUCCESS

        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()
        self.debug_print("action_id", self.get_action_identifier())

        if action_id == 'test_connectivity':
            ret_val = self._handle_test_connectivity(param)
        elif action_id == 'isolate_device':
            ret_val = self._handle_isolate_device(param)
        return ret_val

    def initialize(self):
        # Load the state in initialize, use it to store data
        # that needs to be accessed across actions
        self._state = self.load_state()

        # get the asset config
        config = self.get_config()
        url = config.get('URL')
        self._url = url[:-1] if url[-1] == '/' else url
        self._url += '/mcc/defender/v1/emergency.json'
        self._headers['Content-Type'] = 'application/json'
        self._headers['X-MARK-II-API-KEY'] = self._key = config.get('API Key')
        self._cert = tempfile.NamedTemporaryFile(delete=False)
        lines = config.get('Certificate').split()
        cert = '\n'.join(['-----BEGIN CERTIFICATE-----'] + lines[2:-2] +
                         ['-----END CERTIFICATE-----', ''])
        self._cert.write(cert)
        self._cert.close()
        self._verify = self._cert.name if config.get('Verify') else False
        return phantom.APP_SUCCESS

    def finalize(self):
        os.unlink(self._cert.name)
        # Save the state, this data is saved accross actions and app upgrades
        self.save_state(self._state)
        return phantom.APP_SUCCESS


if __name__ == '__main__':
    import pudb
    import argparse

    pudb.set_trace()
    argparser = argparse.ArgumentParser()
    argparser.add_argument("file", type=argparse.FileType('r'),
                           metavar='FILE', help='Input Test JSON file')
    args = argparser.parse_args()

    in_json = json.loads(args.file.read())
    print(json.dumps(in_json, indent=4))

    connector = Mark2ServerConnector()
    connector.print_progress_message = True
    ret_val = connector._handle_action(json.dumps(in_json), None)
    print (json.dumps(json.loads(ret_val), indent=4))
    exit(0)
