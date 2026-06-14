import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.executor import HFTExecutionEngine

def test_smart_order_routing_maker_rebate():
    engine = HFTExecutionEngine(latency_buffer_ms=0)

    # Spread is equal on both Binance and Bybit (mid is 50000, spread 50000-50000)
    # Maker fee on Binance: 0.0, Taker fee: 0.0004
    # Maker rebate on Bybit: -0.0001, Taker fee: 0.0005
    depths = {
        "Binance": {
            "bids": [[50000, 1.0]],
            "asks": [[50000, 1.0]]
        },
        "Bybit": {
            "bids": [[50000, 1.0]],
            "asks": [[50000, 1.0]]
        }
    }

    # We want to BUY 1.0 BTC.
    # If we are a maker on Bybit, effective price = 50000 * (1 - 0.0001) = 49995
    # If we are a maker on Binance, effective price = 50000 * (1 + 0.0) = 50000
    # SOR should choose Bybit maker first
    res = engine.smart_route_order("BUY", "BTCUSDT", 1.0, depths)

    assert res["fills"][0]["venue"] == "Bybit"
    assert res["fills"][0]["type"] == "maker"

def test_volume_splitting():
    engine = HFTExecutionEngine(latency_buffer_ms=0)

    depths = {
        "Binance": {
            "bids": [[50000, 0.4]],
            "asks": [[50000, 0.4]]
        },
        "Bybit": {
            "bids": [[50000, 0.8]],
            "asks": [[50000, 0.8]]
        }
    }

    # We want to BUY 1.0 BTC.
    res = engine.smart_route_order("BUY", "BTCUSDT", 1.0, depths)
    fills = res["fills"]

    # Should choose Bybit maker first (up to 0.8), then Binance maker (up to 0.2)
    assert len(fills) == 2
    assert fills[0]["venue"] == "Bybit"
    assert fills[0]["qty"] == pytest.approx(0.8)
    assert fills[1]["venue"] == "Binance"
    assert fills[1]["qty"] == pytest.approx(0.2)

def test_slippage_model():
    engine = HFTExecutionEngine(latency_buffer_ms=0)

    depths = {
        "Binance": {
            "bids": [[50000, 10.0]],
            "asks": [[50000, 10.0]]
        }
    }

    # qty = 0.5, no slippage
    res1 = engine.smart_route_order("BUY", "BTCUSDT", 0.5, depths)
    assert res1["average_price"] == 50000.0

    # qty = 1.5, overage = 1.0 -> 10 * 0.1 BTC overage -> 10 * 0.01% = 0.1% slippage
    res2 = engine.smart_route_order("BUY", "BTCUSDT", 1.5, depths)
    assert res2["average_price"] == pytest.approx(50000.0 * 1.001)

def test_return_structure():
    engine = HFTExecutionEngine(latency_buffer_ms=0)
    depths = {
        "Binance": {"bids": [[50000, 1.0]], "asks": [[50000, 1.0]]}
    }
    res = engine.smart_route_order("BUY", "BTCUSDT", 0.1, depths)

    assert "average_price" in res
    assert "cost" in res
    assert "latency_us" in res
    assert "fills" in res
    assert isinstance(res["fills"], list)
    assert res["latency_us"] > 0
