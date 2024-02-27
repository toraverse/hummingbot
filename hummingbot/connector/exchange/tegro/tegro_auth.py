import json

# import asyncio
from collections import OrderedDict

from eth_account import Account, messages

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class TegroAuth(AuthBase):
    """
    Auth class required by Tegro API
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key: str = api_key
        self._api_secret: str = api_secret

    def sign_inner(self, data):
        """
        Sign the provided data using the API secret key.
        """
        message = messages.encode_defunct(text=data)
        signed_data = Account.sign_message(message, private_key=self._api_secret)
        # Convert signature components to bytes before returning
        return signed_data.signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(request.data)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through

    def _sign_order_params(self, params):
        addr = params["WalletAddress"]
        signature = self.sign_inner(addr)

        payload = {
            "signature": signature,
        }
        return payload

    def add_auth_to_params_post(self, params: str):
        payload = {}
        data = json.loads(params) if params is not None else {}
        request_params = OrderedDict(data or {})

        payload = self._sign_order_params(request_params)
        payload = json.dumps(payload)
        return payload
