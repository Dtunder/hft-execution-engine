import random
import time
import requests
import json
import threading

class HFTExecutionEngine:
    """
    Simulates ultra-low latency order routing and execution.
    Calculates execution slippage and returns microsecond order confirmation.
    """
    FEES = {
        "binance": {"taker": 0.0004, "maker": -0.0001},
        "bybit": {"taker": 0.0005, "maker": -0.0001}
    }

    def __init__(self, latency_buffer_ms=0.15):
        self.latency_buffer_ms = latency_buffer_ms
        self.total_orders = 0
        self.successful_fills = 0

    def calculate_slippage(self, side, quantity, mid_price):
        """
        Estimates order book depth slippage. Larger order quantities experience
        progressively higher slippage as they consume bids/asks.
        """
        base_slippage = random.uniform(0.0001, 0.0003)  # 0.01% to 0.03%
        quantity_multiplier = 0.00005 * (quantity ** 1.2)
        total_slippage = base_slippage + quantity_multiplier
        
        if side.upper() == "BUY":
            execution_price = mid_price * (1.0 + total_slippage)
        else:
            execution_price = mid_price * (1.0 - total_slippage)
            
        return execution_price, total_slippage

    def route_order(self, side, symbol, quantity, mid_price):
        """
        Routes order to exchange, simulating network transit time and executing trade.
        """
        self.total_orders += 1
        start_time = time.perf_counter()
        
        # Simulate microsecond hardware execution delay
        time.sleep(self.latency_buffer_ms / 1000.0)
        
        # Calculate market fills and slippage
        exec_price, slippage = self.calculate_slippage(side, quantity, mid_price)
        total_cost = exec_price * quantity
        
        execution_latency_us = (time.perf_counter() - start_time) * 1_000_000.0
        self.successful_fills += 1
        
        print(f"[ENGINE] Order #{self.total_orders} Sent: {side} {quantity} {symbol.upper()} at Mid: ${mid_price:.2f}")
        print(f"         Filled: ${exec_price:.4f} (Slippage: {slippage*100:.3f}%) | Latency: {execution_latency_us:.1f} microseconds")
        
        return {
            "order_id": self.total_orders,
            "status": "FILLED",
            "execution_price": exec_price,
            "quantity": quantity,
            "cost": total_cost,
            "latency_us": execution_latency_us
        }

    def fetch_orderbook(self, exchange, symbol, limit=5):
        """
        Fetches live orderbook depth from testnets. Returns a fallback mock if blocked/fails.
        """
        if exchange == "binance":
            url = f"https://testnet.binancefuture.com/fapi/v1/depth?symbol={symbol}&limit={limit}"
            try:
                resp = requests.get(url, timeout=2)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "bids": [[float(p), float(q)] for p, q in data["bids"]],
                    "asks": [[float(p), float(q)] for p, q in data["asks"]]
                }
            except Exception as e:
                # Fallback mock for Binance
                base_price = 65000.0
                return {
                    "bids": [[base_price - i*10, 0.5 + i] for i in range(1, limit+1)],
                    "asks": [[base_price + i*10, 0.5 + i] for i in range(1, limit+1)]
                }
        elif exchange == "bybit":
            url = f"https://api-testnet.bybit.com/v5/market/orderbook?category=linear&symbol={symbol}&limit={limit}"
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get(url, headers=headers, timeout=2)
                resp.raise_for_status()
                data = resp.json()
                if data.get("retCode") == 0:
                    return {
                        "bids": [[float(p), float(q)] for p, q in data["result"]["b"]],
                        "asks": [[float(p), float(q)] for p, q in data["result"]["a"]]
                    }
                else:
                    raise ValueError("API error")
            except Exception as e:
                # Fallback mock for Bybit (frequently blocked by CloudFront in tests)
                base_price = 65000.0
                return {
                    "bids": [[base_price - i*10, 0.6 + i] for i in range(1, limit+1)],
                    "asks": [[base_price + i*10, 0.6 + i] for i in range(1, limit+1)]
                }

    def smart_route_order(self, side, symbol, quantity):
        """
        Smart Order Routing (SOR) engine to split and execute leveraged perpetual market orders.
        Queries live bid/ask book depth across Binance and Bybit testnets concurrently.
        Executes cheapest taker liquidity first, captures maker fee rebates for remaining parts.
        """
        self.total_orders += 1
        start_time = time.perf_counter()

        # Simulate initial hardware routing delay
        time.sleep(self.latency_buffer_ms / 1000.0)

        books = {}
        def fetch_book_thread(exchange):
            books[exchange] = self.fetch_orderbook(exchange, symbol)

        threads = []
        for ex in ["binance", "bybit"]:
            t = threading.Thread(target=fetch_book_thread, args=(ex,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # Aggregate liquidity
        # format: (price, qty, exchange, fee_rate)
        taker_liquidity = []
        best_maker_price = 0.0

        if side.upper() == "BUY":
            # Taker buys from asks. We want the lowest price.
            for ex, book in books.items():
                fee = self.FEES[ex]["taker"]
                for p, q in book["asks"]:
                    effective_price = p * (1 + fee)
                    taker_liquidity.append((effective_price, p, q, ex, fee))
            taker_liquidity.sort(key=lambda x: x[0])  # Ascending effective price

            # Maker price would be best bid across exchanges
            # We want the max bid price across all top bids
            top_bids = []
            for book in books.values():
                if book["bids"]:
                    top_bids.append(book["bids"][0][0])
            best_maker_price = max(top_bids) if top_bids else 0.0

        else: # SELL
            # Taker sells to bids. We want the highest price.
            for ex, book in books.items():
                fee = self.FEES[ex]["taker"]
                for p, q in book["bids"]:
                    effective_price = p * (1 - fee)
                    taker_liquidity.append((effective_price, p, q, ex, fee))
            taker_liquidity.sort(key=lambda x: x[0], reverse=True)  # Descending effective price

            # Maker price would be best ask across exchanges
            # We want the min ask price across all top asks
            top_asks = []
            for book in books.values():
                if book["asks"]:
                    top_asks.append(book["asks"][0][0])
            best_maker_price = min(top_asks) if top_asks else 0.0

        remaining_qty = quantity
        executed_parts = []
        total_cost = 0.0

        # 1. Execute cheapest taker liquidity first walking the entire limit=5 depth
        for eff_p, p, q, ex, fee in taker_liquidity:
            if remaining_qty <= 0:
                break

            execute_qty = min(remaining_qty, q)
            cost_component = execute_qty * p
            cost_with_fee = execute_qty * eff_p

            executed_parts.append({
                "exchange": ex,
                "role": "taker",
                "price": p,
                "effective_price": eff_p,
                "quantity": execute_qty,
                "fee": execute_qty * p * fee
            })

            total_cost += cost_with_fee
            remaining_qty -= execute_qty

        # 2. Capture maker fee rebates for remaining order parts
        if remaining_qty > 0:
            # Route remaining to the exchange with best maker rebate
            best_maker_ex = min(self.FEES.keys(), key=lambda k: self.FEES[k]["maker"])
            maker_fee_rate = self.FEES[best_maker_ex]["maker"]

            p = best_maker_price
            if side.upper() == "BUY":
                eff_p = p * (1 + maker_fee_rate)
            else:
                eff_p = p * (1 - maker_fee_rate)

            cost_with_fee = remaining_qty * eff_p

            executed_parts.append({
                "exchange": best_maker_ex,
                "role": "maker",
                "price": p,
                "effective_price": eff_p,
                "quantity": remaining_qty,
                "fee": remaining_qty * p * maker_fee_rate
            })

            total_cost += cost_with_fee
            remaining_qty = 0

        execution_latency_us = (time.perf_counter() - start_time) * 1_000_000.0
        self.successful_fills += 1

        avg_price = total_cost / quantity if quantity > 0 else 0.0

        print(f"[SOR] Order #{self.total_orders} Sent: {side} {quantity} {symbol.upper()}")
        print(f"      Avg Fill: ${avg_price:.4f} | Latency: {execution_latency_us:.1f} us")
        for part in executed_parts:
            print(f"      -> {part['exchange'].capitalize()} [{part['role'].upper()}] {part['quantity']:.4f} @ ${part['price']:.2f} (Fee: ${part['fee']:.4f})")

        return {
            "order_id": self.total_orders,
            "status": "FILLED",
            "side": side,
            "symbol": symbol,
            "quantity": quantity,
            "average_price": avg_price,
            "total_cost": total_cost,
            "latency_us": execution_latency_us,
            "parts": executed_parts
        }

if __name__ == "__main__":
    engine = HFTExecutionEngine()
    print("[ENGINE] Initializing Ultra-Low Latency Execution Engine...")
    
    # Test SOR
    engine.smart_route_order("BUY", "BTCUSDT", 2.5)
    engine.smart_route_order("SELL", "BTCUSDT", 1.0)
