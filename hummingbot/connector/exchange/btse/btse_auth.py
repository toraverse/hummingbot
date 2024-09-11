import hashlib
import hmac
import time
from typing import Any, Dict

from hummingbot.connector.exchange.btse import btse_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BtseAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        path = f"/api/{CONSTANTS.PRIVATE_API_VERSION}{request.url.split(CONSTANTS.PRIVATE_API_VERSION)[-1]}"
        nonce = str(int(time.time() * 1e3))

        if request.method == RESTMethod.POST:
            message = path + nonce + request.data
        else:
            message = path + nonce

        signature = self._generate_signature(message=message)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication(nonce, signature))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Btse does not use this
        functionality
        """
        return request  # pass-through

    def _generate_ws_authentication_payload(self) -> Dict[str, Any]:
        """
        Generates the authentication payload required for websocket authentication.
        :return: the authentication payload
        """
        path = "/ws/spot"
        nonce = str(int(time.time() * 1e3))
        message = path + nonce
        signature = self._generate_signature(message=message)

        headers = self.header_for_authentication(nonce, signature)

        payload = {
            "op": CONSTANTS.BTSE_USER_STREAM_CHANNEL,
            "args": [
                headers["request-api"],
                headers["request-nonce"],
                headers["request-sign"],
            ],
        }
        return payload

    def header_for_authentication(self, nonce: str, signature: str) -> Dict[str, str]:
        headers = {
            "request-api": self.api_key,
            "request-nonce": nonce,
            "request-sign": signature,
            "Accept": "application/json;charset=UTF-8",
            "Content-Type": "application/json"
        }

        return headers

    def _generate_signature(self, message: str) -> str:
        signature = hmac.new(bytes(self.secret_key, "latin-1"), msg=bytes(message, "latin-1"), digestmod=hashlib.sha384).hexdigest()

        return signature
