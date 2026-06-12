import pytest
from src.executor import HFTExecutionEngine

def test_smart_route_order_chooses_bybit_for_maker_rebates():
    engine = HFTExecutionEngine(latency_buffer_ms=0.0)

    depths = {
        'Binance': {
            'asks': [(50000, 1.0)],
            'bids': [(49990, 1.0)],
            'taker_fee': 0.0005
        },
        'Bybit': {
            'asks': [(50000, 1.0)],
            'bids': [(49990, 1.0)],
            'maker_rebate': 0.0001,
            'taker_fee': 0.0005
        }
    }

    # BUY order
    res_buy = engine.smart_route_order('BUY', 'BTCUSDT', 0.5, depths)
    assert res_buy['fills'][0]['venue'] == 'Bybit'
    assert res_buy['fills'][0]['qty'] == 0.5
    assert res_buy['average_price'] == 50000.0

    # SELL order
    res_sell = engine.smart_route_order('SELL', 'BTCUSDT', 0.5, depths)
    assert res_sell['fills'][0]['venue'] == 'Bybit'
    assert res_sell['fills'][0]['qty'] == 0.5
    assert res_sell['average_price'] == 49990.0

def test_smart_route_order_slippage():
    engine = HFTExecutionEngine(latency_buffer_ms=0.0)

    depths = {
        'Binance': {
            'asks': [(50000, 1.0)],
            'taker_fee': 0.0
        }
    }

    res = engine.smart_route_order('BUY', 'BTCUSDT', 0.6, depths)
    assert res['average_price'] == pytest.approx(50005.0)

def test_smart_route_order_splits_volume():
    engine = HFTExecutionEngine(latency_buffer_ms=0.0)

    depths = {
        'Binance': {
            'asks': [(50000, 0.4)],
            'taker_fee': 0.0005
        },
        'Bybit': {
            'asks': [(50000, 0.4)],
            'maker_rebate': 0.0001,
            'taker_fee': 0.0005
        }
    }

    res = engine.smart_route_order('BUY', 'BTCUSDT', 0.6, depths)
    assert len(res['fills']) == 2
    assert res['fills'][0]['venue'] == 'Bybit'
    assert res['fills'][0]['qty'] == 0.4
    assert res['fills'][1]['venue'] == 'Binance'
    assert res['fills'][1]['qty'] == pytest.approx(0.2)
