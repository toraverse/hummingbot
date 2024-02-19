import json
import time

# import asyncio
from collections import OrderedDict

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class TegroAuth(AuthBase):
    """
    Auth class required by Tegro API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        base_url = request.url
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(request.data, base_url)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    async def _sign_order_params(self, params):
        signature = params["signature"],

        payload = signature
        return payload

    def add_auth_to_params_post(self, params: str):
        payload = {}
        data = json.loads(params) if params is not None else {}

        request_params = OrderedDict(data or {})

        payload = self._sign_order_params(request_params)
        payload = json.dumps(payload)
        return payload

    @staticmethod
    def _get_timestamp():
        return time.time()
