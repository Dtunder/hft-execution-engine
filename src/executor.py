import random
import time
import os

class HFTExecutionEngine:
    """
    Simulates ultra-low latency order routing and execution.
    Calculates execution slippage and returns microsecond order confirmation.
    """
    def __init__(self, base_latency_ms=1.0, mean_jitter_ms=45.0):
        self.base_latency_ms = base_latency_ms
        self.mean_jitter_ms = mean_jitter_ms
        self.total_orders = 0
        self.successful_fills = 0

        os.makedirs("logs", exist_ok=True)
        # Initialize log file with header
        with open("logs/execution_stats.txt", "w") as f:
            f.write("timestamp,order_id,order_type,side,symbol,quantity,status,exec_price,latency_ms,fill_rate\n")

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

    def log_execution(self, order_id, order_type, side, symbol, quantity, status, exec_price, latency_ms):
        rate = (self.successful_fills / self.total_orders) * 100.0 if self.total_orders > 0 else 0.0
        with open("logs/execution_stats.txt", "a") as f:
            f.write(f"{time.time()},{order_id},{order_type},{side},{symbol},{quantity},{status},{exec_price:.4f},{latency_ms:.4f},{rate:.2f}%\n")

    def route_order(self, side, symbol, quantity, mid_price, order_type="MARKET", limit_price=None):
        """
        Routes order to exchange, simulating network transit time and executing trade.
        """
        self.total_orders += 1
        start_time = time.perf_counter()
        
        # Simulate network jitter using exponential decay probability distribution
        jitter_ms = random.expovariate(1.0 / self.mean_jitter_ms)
        latency_ms = self.base_latency_ms + jitter_ms

        time.sleep(latency_ms / 1000.0)

        actual_latency_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Check IOC latency condition (cancel if latency > 50ms)
        if order_type.upper() == "IOC":
            if actual_latency_ms > 50.0:
                print(f"[ENGINE] Order #{self.total_orders} Cancelled: IOC Exceeded 50ms latency (Actual: {actual_latency_ms:.2f}ms)")
                self.log_execution(self.total_orders, order_type, side, symbol, quantity, "CANCELLED_LATENCY", 0.0, actual_latency_ms)
                return {
                    "order_id": self.total_orders,
                    "status": "CANCELLED",
                    "reason": "Latency > 50ms",
                    "latency_us": actual_latency_ms * 1000.0
                }

        # Calculate market fills and slippage
        exec_price, slippage = self.calculate_slippage(side, quantity, mid_price)
        
        # Check IOC price condition
        if order_type.upper() == "IOC" and limit_price is not None:
            if side.upper() == "BUY" and exec_price > limit_price:
                print(f"[ENGINE] Order #{self.total_orders} Cancelled: IOC Price {exec_price:.4f} > Limit {limit_price:.4f}")
                self.log_execution(self.total_orders, order_type, side, symbol, quantity, "CANCELLED_PRICE", exec_price, actual_latency_ms)
                return {
                    "order_id": self.total_orders,
                    "status": "CANCELLED",
                    "reason": "Price > Limit",
                    "latency_us": actual_latency_ms * 1000.0
                }
            elif side.upper() == "SELL" and exec_price < limit_price:
                print(f"[ENGINE] Order #{self.total_orders} Cancelled: IOC Price {exec_price:.4f} < Limit {limit_price:.4f}")
                self.log_execution(self.total_orders, order_type, side, symbol, quantity, "CANCELLED_PRICE", exec_price, actual_latency_ms)
                return {
                    "order_id": self.total_orders,
                    "status": "CANCELLED",
                    "reason": "Price < Limit",
                    "latency_us": actual_latency_ms * 1000.0
                }

        total_cost = exec_price * quantity
        self.successful_fills += 1
        
        print(f"[ENGINE] Order #{self.total_orders} Sent: {side} {quantity} {symbol.upper()} at Mid: ${mid_price:.2f} ({order_type})")
        print(f"         Filled: ${exec_price:.4f} (Slippage: {slippage*100:.3f}%) | Latency: {actual_latency_ms*1000.0:.1f} microseconds")

        self.log_execution(self.total_orders, order_type, side, symbol, quantity, "FILLED", exec_price, actual_latency_ms)
        
        return {
            "order_id": self.total_orders,
            "status": "FILLED",
            "execution_price": exec_price,
            "quantity": quantity,
            "cost": total_cost,
            "latency_us": actual_latency_ms * 1000.0
        }

if __name__ == "__main__":
    # Test simulation
    engine = HFTExecutionEngine()
    print("[ENGINE] Initializing Ultra-Low Latency Execution Engine...")
    
    # Simulate a burst of market orders and IOC orders
    prices = [58230.50, 58231.00, 58230.20, 58229.80, 58232.00, 58231.50, 58228.00]
    for i, mid_price in enumerate(prices):
        side = "BUY" if i % 2 == 0 else "SELL"
        qty = random.uniform(0.1, 2.5)

        if i % 2 == 1:
            # Send IOC order
            limit = mid_price * 1.0005 if side == "BUY" else mid_price * 0.9995
            engine.route_order(side, "BTCUSDT", qty, mid_price, order_type="IOC", limit_price=limit)
        else:
            # Send MARKET order
            engine.route_order(side, "BTCUSDT", qty, mid_price)

        time.sleep(0.1)
