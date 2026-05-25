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
        
        # Calculate Taker Fee (e.g. 0.035% on Hyperliquid)
        taker_fee_rate = 0.00035
        taker_fee = total_cost * taker_fee_rate

        return {
            "order_id": self.total_orders,
            "status": "FILLED",
            "execution_price": exec_price,
            "quantity": quantity,
            "cost": total_cost,
            "fee": taker_fee,
            "latency_us": execution_latency_us
        }

    def execute_passive_pegging(self, side, symbol, quantity, mid_price, spread=2.0):
        """
        Simulates placing Post-Only maker orders pegged to the dynamic best bid/ask,
        adjusting prices mid-flight as the spread shifts. Maximizes maker fee rebates.
        """
        self.total_orders += 1
        start_time = time.perf_counter()

        # Simulate network delay for placing and adjusting the order
        time.sleep(self.latency_buffer_ms * 2 / 1000.0)

        half_spread = spread / 2.0

        if side.upper() == "BUY":
            # Pegged to best bid
            best_bid = mid_price - half_spread
            # Simulate a slight adverse selection / execution delay causing us to get filled slightly worse than ideal best bid, but better than mid
            execution_price = best_bid + random.uniform(0.0, half_spread * 0.5)
        else:
            # Pegged to best ask
            best_ask = mid_price + half_spread
            # Simulate execution slightly worse than ideal best ask
            execution_price = best_ask - random.uniform(0.0, half_spread * 0.5)

        total_value = execution_price * quantity

        # Calculate Maker Rebate (e.g. 0.01% on Hyperliquid)
        maker_rebate_rate = 0.00010
        maker_rebate = total_value * maker_rebate_rate

        execution_latency_us = (time.perf_counter() - start_time) * 1_000_000.0
        self.successful_fills += 1

        print(f"[ENGINE] Passive Peg Order #{self.total_orders} Sent: {side} {quantity} {symbol.upper()} at Mid: ${mid_price:.2f} (Spread: ${spread:.2f})")
        print(f"         Filled: ${execution_price:.4f} | Maker Rebate Earned: ${maker_rebate:.6f} | Latency: {execution_latency_us:.1f} microseconds")

        return {
            "order_id": self.total_orders,
            "status": "FILLED",
            "execution_price": execution_price,
            "quantity": quantity,
            "cost": total_value,
            "rebate": maker_rebate,
            "latency_us": execution_latency_us
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
