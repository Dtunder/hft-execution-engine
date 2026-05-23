import datetime
import json
import urllib.request
import urllib.error
import time
import random

class PaperPortfolio:
    def __init__(self, initial_capital: float = 50.0):
        self.capital = initial_capital
        self.position = 0.0
        self.entry_price = None
        self.peak_value = initial_capital
        self.trades = []
        self.equity_history = []
        self.initial_capital = initial_capital

    def current_value(self, price: float) -> float:
        return self.capital + self.position * price

    def execute_buy(self, price: float, qty: float, fee_pct: float = 0.0004) -> dict:
        cost = price * qty * (1 + fee_pct)
        if cost > self.capital:
            qty = self.capital / (price * (1 + fee_pct))
            cost = price * qty * (1 + fee_pct)
        self.capital -= cost
        self.position += qty
        self.entry_price = price
        trade = {
            "side": "BUY",
            "price": price,
            "qty": qty,
            "cost": cost,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "pnl": None
        }
        self.trades.append(trade)
        return trade

    def execute_sell(self, price: float, qty: float = None, fee_pct: float = 0.0004) -> dict:
        if self.position <= 0:
            return None
        if qty is None:
            qty = self.position
        qty = min(qty, self.position)
        proceeds = price * qty * (1 - fee_pct)
        pnl = proceeds - (self.entry_price or price) * qty
        self.capital += proceeds
        self.position -= qty
        trade = {
            "side": "SELL",
            "price": price,
            "qty": qty,
            "proceeds": proceeds,
            "pnl": round(pnl, 6),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        self.trades.append(trade)
        return trade

    def snapshot(self, price: float):
        equity = self.current_value(price)
        if equity > self.peak_value:
            self.peak_value = equity
        self.equity_history.append((datetime.datetime.utcnow().isoformat(), equity))

    def summary(self, price: float) -> dict:
        total_value = self.current_value(price)
        total_return_pct = (total_value - self.initial_capital) / self.initial_capital * 100
        wins = [t for t in self.trades if t.get("pnl") is not None and t["pnl"] > 0]
        losses = [t for t in self.trades if t.get("pnl") is not None and t["pnl"] < 0]
        return {
            "initial_capital": self.initial_capital,
            "current_value": round(total_value, 4),
            "return_pct": round(total_return_pct, 4),
            "total_trades": len(self.trades),
            "win_trades": len(wins),
            "loss_trades": len(losses),
            "peak_value": round(self.peak_value, 4)
        }

def fetch_binance_price(symbol: str = "BTCUSDT") -> float:
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return float(data['price'])
    except Exception:
        return 0.0

def run_paper_session(symbol="BTCUSDT", duration_seconds=60, initial_capital=50.0, tick_interval=5):
    portfolio = PaperPortfolio(initial_capital)
    start_time = time.time()
    last_price = 0.0

    while time.time() - start_time < duration_seconds:
        price = fetch_binance_price(symbol)
        if price > 0:
            last_price = price
            if portfolio.position <= 0 and random.random() > 0.7:
                qty = (portfolio.capital * 0.1) / price
                portfolio.execute_buy(price, qty)
            elif portfolio.position > 0 and random.random() > 0.8:
                portfolio.execute_sell(price)

            portfolio.snapshot(price)
            print(f"Current equity: {portfolio.current_value(price):.4f}")

        time.sleep(tick_interval)

    print(portfolio.summary(last_price))

if __name__ == "__main__":
    print("PAPER TRADING MODE — No real money used")
    run_paper_session(duration_seconds=30, initial_capital=50.0)
