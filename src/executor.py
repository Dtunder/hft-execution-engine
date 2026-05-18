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


    def route_adaptive_limit_order(self, side, symbol, quantity, mid_price):
        """
        Routes an adaptive limit order that dynamically adjusts its price every 10ms
        to chase the order book mid-price, optimizing for maker fee rebates.
        """
        self.total_orders += 1
        start_time = time.perf_counter()

        # Simulate bid-ask spread
        spread = 0.50
        maker_rebate_rate = 0.0002  # 0.02% maker fee rebate

        # Determine initial Bid-1 / Ask-1 price level
        if side.upper() == "BUY":
            limit_price = mid_price - (spread / 2)
        else:
            limit_price = mid_price + (spread / 2)

        print(f"[ENGINE] Order #{self.total_orders} Sent: {side} {quantity:.3f} {symbol.upper()} Adaptive Limit Initial: ${limit_price:.2f}")

        filled = False
        chase_iterations = 0

        # Dynamically adjust limit price every 10 milliseconds to chase mid-price
        while not filled:
            time.sleep(0.01)  # 10 milliseconds sleep
            chase_iterations += 1

            # Simulate market mid-price drifting away
            mid_price += random.uniform(-0.8, 0.8)

            # Adjust limit price to new Bid-1 / Ask-1
            if side.upper() == "BUY":
                limit_price = mid_price - (spread / 2)
            else:
                limit_price = mid_price + (spread / 2)

            # Simulate a chance that our limit order gets filled by an aggressive taker
            if random.random() < 0.25 or chase_iterations >= 10:
                filled = True

        exec_price = limit_price
        rebate_amount = exec_price * quantity * maker_rebate_rate

        # Calculate cost factoring in maker rebate
        total_cost = (exec_price * quantity) - rebate_amount if side.upper() == "BUY" else (exec_price * quantity) + rebate_amount

        execution_latency_us = (time.perf_counter() - start_time) * 1_000_000.0
        self.successful_fills += 1

        print(f"         Filled: ${exec_price:.4f} after {chase_iterations} adjustments | Maker Rebate: +${rebate_amount:.4f} | Latency: {execution_latency_us:.1f} microseconds")

        return {
            "order_id": self.total_orders,
            "status": "FILLED_LIMIT",
            "execution_price": exec_price,
            "quantity": quantity,
            "cost": total_cost,
            "latency_us": execution_latency_us,
            "rebate": rebate_amount,
            "adjustments": chase_iterations
        }

if __name__ == "__main__":
    engine = HFTExecutionEngine()
    print("[ENGINE] Initializing Ultra-Low Latency Execution Engine...")
    
    # Simulate a burst of 5 rapid orders using the adaptive limit strategy
    prices = [58230.50, 58231.00, 58230.20, 58229.80, 58232.00]
    for i, mid_price in enumerate(prices):
        side = "BUY" if i % 2 == 0 else "SELL"
        qty = random.uniform(0.1, 2.5)
        engine.route_adaptive_limit_order(side, "BTCUSDT", qty, mid_price)
        time.sleep(0.5)
