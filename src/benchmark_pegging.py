import random
import os
import sys

# Add project root to PYTHONPATH to resolve imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.executor import HFTExecutionEngine

def run_benchmark():
    engine = HFTExecutionEngine()
    print("--- Starting Execution Mode Benchmark ---")

    total_volume = 0.0

    # Taker Metrics
    total_taker_cost = 0.0 # Taker execution cost (base price + slippage + taker fee)
    total_taker_fees = 0.0
    total_taker_slippage_cost = 0.0

    # Maker Metrics
    total_maker_cost = 0.0 # Maker execution cost (better price - maker rebate)
    total_maker_rebates = 0.0

    iterations = 100

    for i in range(iterations):
        side = "BUY" if random.random() > 0.5 else "SELL"
        symbol = "BTCUSDT"
        quantity = random.uniform(0.1, 2.5)
        mid_price = random.uniform(58000, 62000)
        spread = random.uniform(0.5, 5.0)

        # 1. Taker Execution
        taker_result = engine.route_order(side, symbol, quantity, mid_price)
        taker_fee = taker_result["fee"]
        total_taker_fees += taker_fee

        # Calculate slippage cost explicitly for the report
        if side == "BUY":
            slippage_cost = (taker_result["execution_price"] - mid_price) * quantity
            total_taker_cost += taker_result["cost"] + taker_fee
        else:
            slippage_cost = (mid_price - taker_result["execution_price"]) * quantity
            # For a sell, we receive the cost. For comparison, we will track the net capital flow
            # from a buyer's perspective or standardize to absolute transaction cost.
            # Let's standardize:
            # Taker Cost = Slippage Cost + Fees
            total_taker_cost += taker_result["cost"] - taker_fee # We receive less

        total_taker_slippage_cost += slippage_cost

        # 2. Maker Execution (Passive Pegging)
        maker_result = engine.execute_passive_pegging(side, symbol, quantity, mid_price, spread)
        maker_rebate = maker_result["rebate"]
        total_maker_rebates += maker_rebate

        if side == "BUY":
            # For buy, maker captures part of the spread (execution price < mid)
            total_maker_cost += maker_result["cost"] - maker_rebate
        else:
            total_maker_cost += maker_result["cost"] + maker_rebate # We receive more

        total_volume += (mid_price * quantity)

    print("\n--- Benchmark Report ---")
    print(f"Total Volume Traded: ${total_volume:,.2f}")
    print(f"Total Iterations: {iterations}")
    print("\n[ TAKER MODE (Market Orders) ]")
    print(f"Total Slippage Cost: ${total_taker_slippage_cost:,.2f}")
    print(f"Total Taker Fees Paid: ${total_taker_fees:,.2f}")

    print("\n[ MAKER MODE (Passive Pegging) ]")
    print(f"Total Maker Rebates Earned: ${total_maker_rebates:,.2f}")

    # Simple metric: compare the pure frictional costs vs revenues
    # Frictional Cost of Taker = Slippage + Taker Fees
    # Frictional Value of Maker = Maker Rebates + Spread Captured

    print("\n--- Summary ---")
    print("Maker execution allows earning rebates and capturing spread, whereas Taker execution pays fees and crosses the spread.")

if __name__ == "__main__":
    run_benchmark()