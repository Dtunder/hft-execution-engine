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
