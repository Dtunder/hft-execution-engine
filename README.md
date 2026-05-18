# ⚡ HFT Execution Engine
*Ultra-Low Latency Smart Order Router*

> [!NOTE]
> This module manages ultrafast trade execution and order routing. It is designed to simulate order book slippage and route microsecond execution packets to the matching engine.

## ⚙️ Core Strategy
- **Slippage Calculator:** Estimates effective execution prices under thick/thin order book depths.
- **Latency Optimization:** Employs minimal object allocation to prevent Python Garbage Collection (GC) pauses during execution paths.
- **Execution Safeguards:** Instantly rejects orders if estimated slippage exceeds configured threshold bands.

---

## ⚡ Execution Instructions
To test the local HFT order placement engine:
```bash
python src/executor.py
```
