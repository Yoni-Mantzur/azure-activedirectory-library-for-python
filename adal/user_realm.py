#-------------------------------------------------------------------------
# 
# Copyright Microsoft Open Technologies, Inc.
#
# All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http: *www.apache.org/licenses/LICENSE-2.0
#
# THIS CODE IS PROVIDED *AS IS* BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION
# ANY IMPLIED WARRANTIES OR CONDITIONS OF TITLE, FITNESS FOR A
# PARTICULAR PURPOSE, MERCHANTABILITY OR NON-INFRINGEMENT.
#
# See the Apache License, Version 2.0 for the specific language
# governing permissions and limitations under the License.
#
#--------------------------------------------------------------------------

try:
    from urllib.parse import quote, unquote, urlencode
    from urllib.parse import urlparse, urlsplit

except ImportError:
    from urllib import quote, unquote, urlencode
    from urlparse import urlparse, urlsplit

import requests
from . import constants
from . import log
from . import util

USER_REALM_PATH_TEMPLATE = 'common/UserRealm/<user>'

AccountType = constants.UserRealm.account_type
FederationProtocolType = constants.UserRealm.federation_protocol_type


class UserRealm(object):

    def __init__(self, call_context, user_principle, authority):

        self._log = log.Logger("UserRealm", call_context['log_context'])
        self._call_context = call_context
        self._api_version = '1.0'
        self._federation_protocol = None
        self._account_type = None
        self._federation_metadata_url = None
        self._federation_active_auth_url = None
        self._user_principle = user_principle
        self._authority = authority

    @property
    def api_version(self):
        return self._api_version

    @property
    def federation_protocol(self):
        return self._federation_protocol

    @property
    def account_type(self):
        return self._account_type

    @property
    def federation_metadata_url(self):
        return self._federation_metadata_url

    @property
    def federation_active_auth_url(self):
        return self._federation_active_auth_url

    def _get_user_realm_url(self):

        user_realm_url = util.copy_url(self._authority)
        url_encoded_user = quote(self._user_principle, safe='~()*!.\'')
        user_realm_url.path  = USER_REALM_PATH_TEMPLATE.replace('<user>', url_encoded_user)

        user_realm_query = {'api-version':self._api_version}
        user_realm_url.query = urlencode(user_realm_query)
        user_realm_url = util.copy_url(user_realm_url)

        return user_realm_url

    def _validate_constant_value(self, constants, value, case_sensitive):

        if not value:
            return False

        if not case_sensitive:
            value = value.lower()

        return value if value in constnats.values() else False

    def _validate_account_type(self, type):
        return self._validate_constant_value(AccountType, type)

    def _validate_federation_protocol(self, protocol):
        return self._validate_constant_value(FederationProtocolType, protocol)

    def _log_parsed_response(self):

        self._log.debug('UserRealm response:')
        self._log.debug(' AccountType:             {0}'.format(self.account_type))
        self._log.debug(' FederationProtocol:      {0}'.format(self.federation_protocol))
        self._log.debug(' FederationMetatdataUrl:  {0}'.format(self.federation_metadata_url))
        self._log.debug(' FederationActiveAuthUrl: {0}'.format(self.federation_active_auth_url))

    def _parse_discovery_response(self, body, callback):

        self._log.debug("Discovery response:\n{0}".format(body))

        response = None
        try:
            response = json.loads(body)
        except Exception as exp:
            callback(self._log.create_error('Parsing realm discovery response JSON failed: {0}'.format(body)))
            return

        account_type = self._validate_account_type(response['account_type'])
        if not account_type:
            callback(self._log.create_error('Cannot parse account_type: {0}'.format(account_type)))
            return
        self._account_type = account_type

        if self._account_type == AccountType['Federated']:
            protocol = self._validate_federation_protocol(response['federation_protocol'])

            if not protocol:
                callback(self._log.create_error('Cannot parse federation protocol: {0}'.format(protocol)))
                return

            self._federation_protocol = protocol
            self._federation_metadata_url = response['federation_metadata_url']
            self._federation_active_auth_url = response['federation_active_auth_url']

        self._log_parsed_response()
        callback(None)

    def discover(self, callback):

        options = util.create_request_options(self, {'headers': {'Accept':'application/json'}})
        user_realm_url = self._get_user_realm_url()
        self._log.debug("Performing user realm discovery at: {0}".format(user_realm_url.geturl()))

        operation = 'User Realm Discovery'
        try:
            resp = requests.get(user_realm_url, headers=options['headers'])
            util.log_return_correlation_id(self._log, operation, resp)

            if not util.is_http_success(resp.status_code):
                return_error_string = "{0} request returned http error: {1}".format(operation, resp.status_code)
                error_response = ""
                if resp.body:
                    return_error_string += " and server response: {0}".format(resp.body)
                    try:
                        error_response = resp.json()
                    except:
                        pass

                callback(self._log.create_error(return_error_string), error_response)
                return

            else:
                self._parse_discovery_response(resp.body, callback)

        except Exception as exp:
            self._log.error("{0} request failed".format(operation), exp)
            callback(exp, None)
            return