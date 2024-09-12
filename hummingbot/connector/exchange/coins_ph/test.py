import asyncio
import datetime
import hashlib
import hmac
import json
import time
from base64 import b64decode, b64encode

import aiohttp
import ujson
import websockets

# constants
client_key_id = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
client_secret = "XXXXXXXX"
REST_PRIVATE_URL = "https://api.pro.coins.ph/openapi/"
REST_PUBLIC_URL = "https://api.pro.coins.ph/openapi/"
WSS_PRIVATE_URL = "wss://wsapi.pro.coins.ph"
WSS_PUBLIC_URL = "wss://wsapi.pro.coins.ph/openapi/quote/ws/v3"
pair = "BTC-USDT"


# Bearer
async def bearer():
    async with aiohttp.ClientSession() as client:

        nonce = str(int(time.time() * 1000))
        timestamp = datetime.datetime.utcnow().isoformat()[:-3] + 'Z'
        signature = b64encode(hmac.new(b64decode(client_secret), msg = bytes(client_key_id + nonce + timestamp, 'utf-8'), digestmod = hashlib.sha256).digest()).decode('utf-8')
        print(signature)

        data = {
            'client_key_id': client_key_id,
            'timestamp': timestamp,
            'nonce': nonce,
            'signature': signature}
        post_json = json.dumps(data)
        print(post_json)

        headers = {
            "Content-Type": 'application/json'
        }

        url = f"{REST_PRIVATE_URL}/v1/authenticate"
        response = await client.post(url, data=post_json, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if "error_code" in parsed_response:
            raise IOError(f"{url} API call failed, response: {parsed_response['error_message']}")

        return parsed_response


async def instrument_data(token):
    async with aiohttp.ClientSession() as client:

        headers = {
            "authorization": f"Bearer {token}",
            "Content-Type": 'application/json'
        }

        url = f"{REST_PRIVATE_URL}/v1/account/instrument-data"
        response = await client.get(url, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if "error_code" in parsed_response:
            raise IOError(f"{url} API call failed, response: {parsed_response['error_message']}")

        return parsed_response


async def wallet_balances(token):
    async with aiohttp.ClientSession() as client:

        headers = {
            "authorization": f"Bearer {token}",
            "Content-Type": 'application/json'
        }

        url = f"{REST_PRIVATE_URL}/v1/account/wallets"
        response = await client.get(url, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if "error_code" in parsed_response:
            raise IOError(f"{url} API call failed, response: {parsed_response['error_message']}")

        return parsed_response


async def trades(token):
    async with aiohttp.ClientSession() as client:

        headers = {
            "authorization": f"Bearer {token}",
            "Content-Type": 'application/json'
        }

        url = f"{REST_PRIVATE_URL}/v1/account/trades"
        response = await client.get(url, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if "error_code" in parsed_response:
            raise IOError(f"{url} API call failed, response: {parsed_response['error_message']}")

        return parsed_response


async def orders(token):
    async with aiohttp.ClientSession() as client:

        headers = {
            "authorization": f"Bearer {token}",
            "Content-Type": 'application/json'
        }

        url = f"{REST_PRIVATE_URL}/v1/account/order-positions"
        response = await client.get(url, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if "error_code" in parsed_response:
            raise IOError(f"{url} API call failed, response: {parsed_response['error_message']}")

        return parsed_response


async def transactions(token):
    async with aiohttp.ClientSession() as client:

        headers = {
            "authorization": f"Bearer {token}",
            "Content-Type": 'application/json'
        }

        url = f"{REST_PRIVATE_URL}/v1/account/account-transactions"
        response = await client.get(url, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if "error_code" in parsed_response:
            raise IOError(f"{url} API call failed, response: {parsed_response['error_message']}")

        return parsed_response


async def start_ws_private_client(token):
    async def ws_loop():
        headers = {
            "authorization": f"Bearer {token}",
            "Content-Type": 'application/json'
        }
        async with websockets.connect(WSS_PRIVATE_URL, extra_headers=headers) as ws:
            params = {
                "type": "SUBSCRIBE",
                "channels": [
                    "WALLET_BALANCES",
                    "WORKING_ORDERS",
                    "ORDER_POSITIONS"
                ]
            }
            await ws.send(ujson.dumps(params))
            while True:
                print("read:", await ws.recv())

    try:
        await ws_loop()
    except websockets.exceptions.ConnectionClosed as ex:
        print("connection closed", ex)
    except KeyboardInterrupt:
        pass


async def start_ws_public_client():
    async def ws_loop():
        async with websockets.connect(WSS_PUBLIC_URL) as ws:
            print("connected")
            depth_params = {
                "method": "SUBSCRIBE",
                "params": ["btcusdt@depth@100ms"],
                "id": 1,
            }
            trade_params = {
                "method": "SUBSCRIBE",
                "params": ["btcusdt@trade"],
                "id": 2,
            }
            await ws.send(json.dumps(depth_params))
            await ws.send(json.dumps(trade_params))
            while True:
                data = await ws.recv()
                print(json.dumps(data, indent=4))

    try:
        await ws_loop()
    except websockets.exceptions.ConnectionClosed as ex:
        print("connection closed", ex)
    except KeyboardInterrupt:
        pass


async def main():
    # try:
    #     token = await asyncio.wait_for(bearer(), timeout=10.0)
    #     print(json.dumps(token, indent=4))
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')

    # try:
    #     instruments = await asyncio.wait_for(instrument_data(token["token"]), timeout=10.0)
    #     print(json.dumps(instruments, indent=4))
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')

    # try:
    #     wallets = await asyncio.wait_for(wallet_balances(token["token"]), timeout=10.0)
    #     print(json.dumps(wallets, indent=4))
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')
    #
    # await asyncio.sleep(1.0)

    # try:
    #     trade_history = await asyncio.wait_for(trades(token["token"]), timeout=10.0)
    #     print(json.dumps(trade_history, indent=4))
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')
    #
    # # await asyncio.sleep(1.0)

    # try:
    #     order_history = await asyncio.wait_for(orders(token["token"]), timeout=10.0)
    #     print(json.dumps(order_history, indent=4))
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')

    # try:
    #     transaction_history = await asyncio.wait_for(transactions(token["token"]), timeout=10.0)
    #     print(json.dumps(transaction_history, indent=4))
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')

    # WSS Private
    # try:
    #     await start_ws_private_client(token["token"])
    # except asyncio.CancelledError:
    #     raise
    # except asyncio.TimeoutError:
    #     print('timeout!')

    # WSS Public
    try:
        await start_ws_public_client()
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        print('timeout!')

asyncio.run(main())
