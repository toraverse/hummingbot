import asyncio
import json
from unittest import TestCase, mock

from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TegroAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.auth = TegroAuth(api_key=self.api_key, api_secret=self.secret_key)

    def async_run_with_timeout(self, coroutine):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout=1))

    @mock.patch("hummingbot.connector.exchange.tegro.tegro_auth.Account.sign_message")
    @mock.patch("hummingbot.connector.exchange.tegro.tegro_auth.messages.encode_defunct")
    def test_sign_order_params_post_request(self, mock_encode_defunct, mock_sign_message):
        # Mocking dependencies
        mock_encode_defunct.return_value = "encoded_data"
        mock_sign_message.return_value = mock.Mock(signature={"r": 1, "s": 2, "v": 3})

        # Test data
        request_data = {"chainID": 80001, "WalletAddress": "testApiKey"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(request_data),
            is_auth_required=True,
        )

        # Run the test
        signed_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        # Assertions
        mock_encode_defunct.assert_called_once_with(text="testApiKey")
        mock_sign_message.assert_called_once_with("encoded_data", private_key=self.secret_key)
        self.assertEqual(json.loads(signed_request.data), {"signature": {"r": 1, "s": 2, "v": 3}})
