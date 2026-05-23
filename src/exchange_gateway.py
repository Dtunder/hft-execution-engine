import urllib.request
import json
import ssl

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        raise e

class BinanceAdapter:
    def __init__(self, config):
        self.config = config

    def get_price(self, symbol, side) -> float:
        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
        data = fetch_json(url)
        if side.upper() == "BUY":
            return float(data["askPrice"])
        elif side.upper() == "SELL":
            return float(data["bidPrice"])
        return 0.0

    def get_orderbook(self, symbol) -> dict:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=5"
        return fetch_json(url)

    def place_order(self, symbol, side, qty, order_type) -> dict:
        price = self.get_price(symbol, side)
        return {"simulated": True, "price": price, "qty": qty}


class BybitAdapter:
    def __init__(self, config):
        self.config = config

    def get_price(self, symbol, side) -> float:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
        data = fetch_json(url)
        item = data["result"]["list"][0]
        if side.upper() == "BUY":
            return float(item["ask1Price"])
        elif side.upper() == "SELL":
            return float(item["bid1Price"])
        return 0.0

    def get_orderbook(self, symbol) -> dict:
        url = f"https://api.bybit.com/v5/market/orderbook?category=spot&symbol={symbol}"
        return fetch_json(url)

    def place_order(self, symbol, side, qty, order_type) -> dict:
        price = self.get_price(symbol, side)
        return {"simulated": True, "price": price, "qty": qty}


class ExchangeGateway:
    def __init__(self, exchanges: list = None):
        if exchanges is None:
            exchanges = [{"name": "binance", "testnet": True}]

        self.adapters = {}
        for config in exchanges:
            name = config.get("name", "").lower()
            if name == "binance":
                self.adapters[name] = BinanceAdapter(config)
            elif name == "bybit":
                self.adapters[name] = BybitAdapter(config)

    def get_best_price(self, symbol: str, side: str) -> dict:
        best_price = None
        best_exchange = None
        all_prices = {}

        for name, adapter in self.adapters.items():
            try:
                price = adapter.get_price(symbol, side)
                all_prices[name] = price

                if best_price is None:
                    best_price = price
                    best_exchange = name
                else:
                    if side.upper() == "BUY":
                        if price < best_price:
                            best_price = price
                            best_exchange = name
                    elif side.upper() == "SELL":
                        if price > best_price:
                            best_price = price
                            best_exchange = name
            except Exception as e:
                pass

        return {
            "best_exchange": best_exchange,
            "best_price": best_price,
            "all_prices": all_prices
        }

    def get_total_balance(self, asset: str = "USDT") -> dict:
        by_exchange = {}
        total = 0.0
        for name in self.adapters:
            # Simulate balance fetch
            simulated_balance = 1000.0
            by_exchange[name] = simulated_balance
            total += simulated_balance

        return {
            "total": total,
            "by_exchange": by_exchange
        }

    def place_best_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET") -> dict:
        best_info = self.get_best_price(symbol, side)
        best_exchange = best_info.get("best_exchange")
        if not best_exchange:
            raise Exception("Could not find a price to place best order.")

        adapter = self.adapters[best_exchange]
        order_response = adapter.place_order(symbol, side, quantity, order_type)
        return {
            "exchange": best_exchange,
            "order": order_response
        }

    def get_spread(self, symbol: str) -> dict:
        by_exchange = {}
        max_bid = -1.0
        min_ask = float('inf')

        for name, adapter in self.adapters.items():
            try:
                ob = adapter.get_orderbook(symbol)
                bid = 0.0
                ask = 0.0

                if name == "binance":
                    if ob.get("bids"): bid = float(ob["bids"][0][0])
                    if ob.get("asks"): ask = float(ob["asks"][0][0])
                elif name == "bybit":
                    if ob.get("result", {}).get("b"): bid = float(ob["result"]["b"][0][0])
                    if ob.get("result", {}).get("a"): ask = float(ob["result"]["a"][0][0])

                spread = ask - bid if ask and bid else 0.0
                by_exchange[name] = {
                    "bid": bid,
                    "ask": ask,
                    "spread": spread
                }

                if bid > max_bid and bid > 0:
                    max_bid = bid
                if ask < min_ask and ask > 0:
                    min_ask = ask

            except Exception as e:
                pass

        cross_spread = max_bid - min_ask if max_bid > 0 and min_ask < float('inf') and max_bid > min_ask else 0.0

        return {
            "by_exchange": by_exchange,
            "cross_exchange_spread": cross_spread
        }

if __name__ == "__main__":
    gw = ExchangeGateway([
        {"name": "binance", "testnet": False},
        {"name": "bybit", "testnet": False}
    ])

    best = gw.get_best_price("BTCUSDT", "BUY")
    print("Best buy price:", best)

    spread = gw.get_spread("BTCUSDT")
    print("Spread analysis:", spread)

    if spread["cross_exchange_spread"] > 0:
        print(f"ARBITRAGE OPPORTUNITY: {spread['cross_exchange_spread']:.2f}")
