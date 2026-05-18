import pytest
from src.executor import HFTExecutionEngine

def test_smart_route_order_buy(mocker):
    engine = HFTExecutionEngine(latency_buffer_ms=0)

    # Mock fetch_orderbook to return controlled data
    def mock_fetch_orderbook(exchange, symbol, limit=5):
        if exchange == "binance":
            return {
                "bids": [[100.0, 1.0]],
                "asks": [[101.0, 1.0], [102.0, 1.0]]
            }
        elif exchange == "bybit":
            return {
                "bids": [[100.0, 1.0]],
                "asks": [[100.5, 0.5], [103.0, 1.0]]
            }

    mocker.patch.object(engine, 'fetch_orderbook', side_effect=mock_fetch_orderbook)

    # Buy 2.0 quantity
    # Binance asks: 101.0 (qty 1), 102.0 (qty 1) -> Taker fee 0.0004 -> eff prices: 101.0404, 102.0408
    # Bybit asks: 100.5 (qty 0.5), 103.0 (qty 1) -> Taker fee 0.0005 -> eff prices: 100.55025, 103.0515
    # Cheapest:
    # 1. Bybit 100.5 (qty 0.5)
    # 2. Binance 101.0 (qty 1.0)
    # 3. Binance 102.0 (qty 0.5)  <-- the new implementation consumes the depth, so it gets filled as Taker

    result = engine.smart_route_order("BUY", "BTCUSDT", 2.0)

    assert result["status"] == "FILLED"
    assert result["quantity"] == 2.0

    parts = result["parts"]
    assert len(parts) == 3

    assert parts[0]["exchange"] == "bybit"
    assert parts[0]["role"] == "taker"
    assert parts[0]["quantity"] == 0.5
    assert parts[0]["price"] == 100.5

    assert parts[1]["exchange"] == "binance"
    assert parts[1]["role"] == "taker"
    assert parts[1]["quantity"] == 1.0
    assert parts[1]["price"] == 101.0

    assert parts[2]["exchange"] == "binance"
    assert parts[2]["role"] == "taker"
    assert parts[2]["quantity"] == 0.5
    assert parts[2]["price"] == 102.0

def test_smart_route_order_sell(mocker):
    engine = HFTExecutionEngine(latency_buffer_ms=0)

    # Mock fetch_orderbook to return controlled data
    def mock_fetch_orderbook(exchange, symbol, limit=5):
        if exchange == "binance":
            return {
                "bids": [[99.0, 1.0], [98.0, 1.0]],
                "asks": [[101.0, 1.0]]
            }
        elif exchange == "bybit":
            return {
                "bids": [[99.5, 0.5], [97.0, 1.0]],
                "asks": [[100.5, 1.0]]
            }

    mocker.patch.object(engine, 'fetch_orderbook', side_effect=mock_fetch_orderbook)

    # Sell 2.0 quantity
    # Binance bids: 99.0 (qty 1), 98.0 (qty 1) -> Taker fee 0.0004 -> eff prices: 98.9604, 97.9608
    # Bybit bids: 99.5 (qty 0.5), 97.0 (qty 1) -> Taker fee 0.0005 -> eff prices: 99.45025, 96.9515
    # Highest:
    # 1. Bybit 99.5 (qty 0.5)
    # 2. Binance 99.0 (qty 1.0)
    # 3. Binance 98.0 (qty 0.5) <-- consumes depth

    result = engine.smart_route_order("SELL", "BTCUSDT", 2.0)

    assert result["status"] == "FILLED"
    assert result["quantity"] == 2.0

    parts = result["parts"]
    assert len(parts) == 3

    assert parts[0]["exchange"] == "bybit"
    assert parts[0]["role"] == "taker"
    assert parts[0]["quantity"] == 0.5
    assert parts[0]["price"] == 99.5

    assert parts[1]["exchange"] == "binance"
    assert parts[1]["role"] == "taker"
    assert parts[1]["quantity"] == 1.0
    assert parts[1]["price"] == 99.0

    assert parts[2]["exchange"] == "binance"
    assert parts[2]["role"] == "taker"
    assert parts[2]["quantity"] == 0.5
    assert parts[2]["price"] == 98.0
