import random
import time

class HFTExecutionEngine:
    """
    Simulates ultra-low latency order routing and execution.
    Calculates execution slippage and returns microsecond order confirmation.
    """
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


    def smart_route_order(self, side, symbol, qty, depths):
        import time
        start_ns = time.perf_counter_ns()

        time.sleep(self.latency_buffer_ms / 1000.0)

        slippage_pct = 0.0
        if qty > 0.5:
            overage = qty - 0.5
            slippage_pct = (overage / 0.1) * 0.0001

        levels = []
        for venue, book in depths.items():
            fee = book.get("taker_fee", 0.0)
            if venue.lower() == "bybit" and "maker_rebate" in book:
                fee = -book["maker_rebate"]
            elif "fee" in book:
                fee = book["fee"]

            if side.upper() == "BUY":
                for price, size in book.get("asks", []):
                    eff_price = price * (1 + slippage_pct) * (1 + fee)
                    levels.append((eff_price, price, size, venue, fee))
            else:
                for price, size in book.get("bids", []):
                    eff_price = price * (1 - slippage_pct) * (1 - fee)
                    levels.append((eff_price, price, size, venue, fee))

        if side.upper() == "BUY":
            levels.sort(key=lambda x: x[0])
        else:
            levels.sort(key=lambda x: x[0], reverse=True)

        remaining_qty = qty
        total_cost = 0.0
        fills = []

        for eff_price, price, size, venue, fee in levels:
            if remaining_qty <= 0:
                break

            fill_qty = min(remaining_qty, size)

            if side.upper() == "BUY":
                exec_price = price * (1 + slippage_pct)
                cost = fill_qty * exec_price * (1 + fee)
            else:
                exec_price = price * (1 - slippage_pct)
                cost = fill_qty * exec_price * (1 - fee)

            remaining_qty -= fill_qty
            total_cost += cost
            fills.append({
                "venue": venue,
                "price": exec_price,
                "qty": fill_qty,
                "fee": fee
            })

        filled_qty = qty - remaining_qty
        if filled_qty > 0:
            avg_price = sum(f["price"] * f["qty"] for f in fills) / filled_qty
        else:
            avg_price = 0.0

        latency_us = (time.perf_counter_ns() - start_ns) / 1000.0

        return {
            "average_price": avg_price,
            "cost": total_cost,
            "latency_us": latency_us,
            "fills": fills
        }

if __name__ == "__main__":

    engine = HFTExecutionEngine()
    print("[ENGINE] Initializing Ultra-Low Latency Execution Engine...")
    
    # Simulate a burst of 5 rapid market orders
    prices = [58230.50, 58231.00, 58230.20, 58229.80, 58232.00]
    for i, mid_price in enumerate(prices):
        side = "BUY" if i % 2 == 0 else "SELL"
        qty = random.uniform(0.1, 2.5)
        engine.route_order(side, "BTCUSDT", qty, mid_price)
        time.sleep(0.5)
