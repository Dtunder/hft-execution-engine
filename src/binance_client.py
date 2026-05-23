import urllib.request
import urllib.parse
import urllib.error
import hmac
import hashlib
import time
import json
import os

class BinanceClient:
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.api_key = api_key or os.environ.get("BINANCE_API_KEY")
        self.api_secret = api_secret or os.environ.get("BINANCE_API_SECRET")
        self.testnet = testnet
        if self.testnet:
            self.base_url = "https://testnet.binance.vision"
        else:
            self.base_url = "https://api.binance.com"

    def _sign(self, params: dict) -> str:
        query_string = urllib.parse.urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False):
        if params is None:
            params = {}
        else:
            params = params.copy()

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params = dict(sorted(params.items()))
            params['signature'] = self._sign(params)

        query_string = urllib.parse.urlencode(params)

        url = self.base_url + endpoint
        if query_string and method in ["GET", "DELETE"]:
            url += "?" + query_string
            data = None
        elif query_string:
            data = query_string.encode('utf-8')
        else:
            data = None

        req = urllib.request.Request(url, data=data, method=method)
        if self.api_key:
            req.add_header('X-MBX-APIKEY', self.api_key)

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode('utf-8'))
            except json.JSONDecodeError:
                return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def get_server_time(self) -> int:
        res = self._request("GET", "/api/v3/time")
        return res.get("serverTime", 0)

    def get_price(self, symbol: str) -> float:
        res = self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})
        return float(res.get("price", 0.0))

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        return self._request("GET", "/api/v3/depth", {"symbol": symbol, "limit": limit})

    def get_account_balance(self) -> dict:
        res = self._request("GET", "/api/v3/account", signed=True)
        if "balances" not in res:
            return res
        balances = {}
        for b in res["balances"]:
            free = float(b["free"])
            locked = float(b["locked"])
            if free > 0 or locked > 0:
                balances[b["asset"]] = {"free": free, "locked": locked}
        return balances

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity
        }
        return self._request("POST", "/api/v3/order", params, signed=True)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, time_in_force: str = "GTC") -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "quantity": quantity,
            "price": price,
            "timeInForce": time_in_force
        }
        return self._request("POST", "/api/v3/order", params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._request("DELETE", "/api/v3/order", params, signed=True)

    def get_open_orders(self, symbol: str = None) -> list:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v3/openOrders", params, signed=True)

    def get_order_status(self, symbol: str, order_id: int) -> dict:
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return self._request("GET", "/api/v3/order", params, signed=True)

if __name__ == "__main__":
    client = BinanceClient(testnet=True)

    # Public endpoints (no keys needed):
    print("Server time:", client.get_server_time())
    print("BTC price:", client.get_price("BTCUSDT"))
    ob = client.get_orderbook("BTCUSDT", limit=5)
    if "bids" in ob and "asks" in ob and len(ob["bids"]) > 0 and len(ob["asks"]) > 0:
        print("Top bid:", ob["bids"][0], "Top ask:", ob["asks"][0])
    else:
        print("Orderbook:", ob)

    # Authenticated endpoints (only run if env vars set):
    if os.environ.get("BINANCE_API_KEY"):
        balance = client.get_account_balance()
        print("Balances:", balance)
    else:
        print("BINANCE_API_KEY not set — skipping authenticated tests")
