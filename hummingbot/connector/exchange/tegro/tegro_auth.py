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

# import json
# from collections import OrderedDict
# import eth_account
# import binascii
# from eth_account.messages import encode_structured_data
# from eth_utils import to_hex

# from hummingbot.core.web_assistant.auth import AuthBase
# from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


# class TegroAuth(AuthBase):
#     """
#     Auth class required by Tegro API
#     """

#     def __init__(self, api_key: str, api_secret: str):
#         self._api_key: str = api_key
#         self._api_secret: str = api_secret
#         private_key_bytes = binascii.unhexlify(api_secret[2:])  # Remove '0x' prefix and decode from hex
#         self.wallet = eth_account.Account.from_key(private_key_bytes)

#     def sign_inner(self, wallet, data):
#         structured_data = encode_structured_data(data)
#         signed = wallet.sign_message(structured_data)
#         return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}

#     def sign_l1_action(self, wallet):
#         address = self._api_key
#         data = {"address": address}
#         return self.sign_inner(wallet, data["address"])

#     async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
#         base_url = request.url
#         if request.method == RESTMethod.POST:
#             request.data = self.add_auth_to_params_post(request.data, base_url)
#         return request

#     async def ws_authenticate(self, request: WSRequest) -> WSRequest:
#         return request  # pass-through

#     async def _sign_order_params(self, params):
#         address = params["WalletAddress"]
#         signature = await self.sign_inner(self.wallet, address)

#         payload = signature
#         return payload

#     def add_auth_to_params_post(self, params: str):
#         payload = {}
#         data = json.loads(params) if params is not None else {}

#         request_params = OrderedDict(data or {})

#         payload = self._sign_order_params(request_params)
#         payload = json.dumps(payload)
#         return payload
