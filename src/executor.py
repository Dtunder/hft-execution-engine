import time

FEES = {
    "Binance": {"maker": 0.0000, "taker": 0.0004},
    "Bybit": {"maker": -0.0001, "taker": 0.0005}  # Bybit offers maker rebates
}

class HFTExecutionEngine:
    """
    Simulates ultra-low latency order routing and execution.
    Calculates execution slippage and returns microsecond order confirmation.
    """
    def __init__(self, latency_buffer_ms=0.15):
        self.latency_buffer_ms = latency_buffer_ms
        self.total_orders = 0
        self.successful_fills = 0

    def smart_route_order(self, side, symbol, qty, depths):
        """
        Smart Order Routing: given Binance and Bybit depth dicts, execute the order
        by splitting volume across both venues to minimize cost (taker fees vs maker rebates).
        """
        start_time = time.perf_counter_ns()
        
        if self.latency_buffer_ms > 0:
            time.sleep(self.latency_buffer_ms / 1000.0)

        options = []
        for venue, depth in depths.items():
            fees = FEES.get(venue, {"maker": 0.0, "taker": 0.0})
            maker_fee = fees["maker"]
            taker_fee = fees["taker"]
            
            if side.upper() == "BUY":
                # Maker options (posting Bids)
                for price, vol in depth.get("bids", []):
                    eff_price = price * (1 + maker_fee)
                    options.append({"venue": venue, "type": "maker", "price": price, "vol": vol, "eff_price": eff_price})
                # Taker options (hitting Asks)
                for price, vol in depth.get("asks", []):
                    eff_price = price * (1 + taker_fee)
                    options.append({"venue": venue, "type": "taker", "price": price, "vol": vol, "eff_price": eff_price})
            else:
                # Maker options (posting Asks)
                for price, vol in depth.get("asks", []):
                    eff_price = price * (1 - maker_fee)
                    options.append({"venue": venue, "type": "maker", "price": price, "vol": vol, "eff_price": eff_price})
                # Taker options (hitting Bids)
                for price, vol in depth.get("bids", []):
                    eff_price = price * (1 - taker_fee)
                    options.append({"venue": venue, "type": "taker", "price": price, "vol": vol, "eff_price": eff_price})

        # Sort to minimize cost
        # For BUY, lower effective price is better
        # For SELL, higher effective price is better (proceeds)
        reverse_sort = True if side.upper() == "SELL" else False
        options.sort(key=lambda x: x["eff_price"], reverse=reverse_sort)
        
        rem_qty = qty
        fills = []
        
        for opt in options:
            if rem_qty <= 0:
                break
            fill_qty = min(rem_qty, opt["vol"])
            rem_qty -= fill_qty
            fills.append({
                "venue": opt["venue"],
                "type": opt["type"],
                "price": opt["price"],
                "qty": fill_qty,
                "eff_price": opt["eff_price"]
            })

        if rem_qty > 0 and options:
            # If not enough liquidity, fill the rest at the last best available price
            last_opt = options[-1]
            fills.append({
                "venue": "Fallback",
                "type": "fallback",
                "price": last_opt["price"],
                "qty": rem_qty,
                "eff_price": last_opt["eff_price"]
            })

        # Calculate base average price
        base_avg_price = sum(f["price"] * f["qty"] for f in fills) / qty if qty > 0 else 0.0
        total_eff_value = sum(f["eff_price"] * f["qty"] for f in fills)
        
        # Add slippage model: for qty > 0.5 BTC, apply 0.01% slippage per 0.1 BTC overage
        slippage_pct = 0.0
        if qty > 0.5:
            overage = qty - 0.5
            slippage_pct = (overage / 0.1) * 0.0001

        if side.upper() == "BUY":
            average_price = base_avg_price * (1 + slippage_pct)
            slippage_cost = (average_price - base_avg_price) * qty
            cost = total_eff_value + slippage_cost
        else:
            average_price = base_avg_price * (1 - slippage_pct)
            slippage_cost = (base_avg_price - average_price) * qty
            cost = total_eff_value - slippage_cost

        end_time = time.perf_counter_ns()
        latency_us = (end_time - start_time) / 1000.0
        
        return {
            "average_price": average_price,
            "cost": cost,
            "latency_us": latency_us,
            "fills": fills
        }

if __name__ == "__main__":
    engine = HFTExecutionEngine()
    print("[ENGINE] Initializing Ultra-Low Latency Execution Engine...")
