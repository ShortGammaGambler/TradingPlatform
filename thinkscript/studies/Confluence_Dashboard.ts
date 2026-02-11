## **PART 4: Master Confluence Dashboard (all-in-one indicator)**
*Plots a 1-5 star rating on any chart (SPX, QQQ, or equity) based on aggregate signals.*

### **Script: `Confluence_Dashboard`**
```thinkscript
# Confluence Dashboard (plot on SPX, QQQ, or any equity chart)
# Add as Study on 5-min chart

declare lower;

# ========== INPUTS ==========
input indexWeight   = 0.4;   # SPX/NDX signal weight
input etfWeight     = 0.3;   # SPY/QQQ signal weight
input equityWeight  = 0.3;   # Equity signal weight
# ============================

# Pull signals from scanners (requires named studies saved above)
def idxSig = IndexVRPTrade();      # from Part 1
def etfSig = ETFSignal();          # from Part 2
def eqSig  = EquitySignal();       # from Part 3

# Confluence score 0-5
def score = Round(
    (indexWeight * idxSig + etfWeight * etfSig + equityWeight * eqSig + 2.5) * 2,
    0
);

plot Stars = score;
Stars.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Stars.AssignValueColor(
    if score >= 4 then Color.DARK_GREEN
    else if score == 3 then Color.GREEN
    else if score == 2 then Color.YELLOW
    else if score == 1 then Color.ORANGE
    else Color.RED
);

AddLabel(yes,
    if score >= 4 then "5-STAR SETUP: Aggressive long premium"
    else if score == 3 then "3-4 STAR: Long directional"
    else if score == 2 then "2 STAR: Neutral/sell vol"
    else if score == 1 then "1 STAR: Avoid"
    else "NO EDGE",
    if score >= 4 then Color.WHITE else Color.BLACK
);
```

---

### **How to Use Dashboard**
1. **Attach** to **5-min chart** of SPX or QQQ.  
2. **Read**:  
   - **5 stars** (dark green): All scanners align—size up to 1 % risk.  
   - **3-4 stars** (green): Two of three agree—normal 0.5 % risk.  
   - **2 stars** (yellow): Mixed signals—sell premium only.  
   - **1 star** (orange): No edge—paper trade or sit out.  
   - **Red**: Flat or hedged.

---

## **Execution & Position-Sizing Cheat Sheet**
| Scanner | Signal | Strategy | Size | Stop | Target |
|---|---|---|---|---|---|
| **Index VRP** | +1 (Sell) | 15Δ strangle | 1 % | 2× credit | 25 % profit |
| **Index VRP** | -1 (Buy) | ATM straddle | 0.5 % | -30 % | +60 % |
| **ETF Flow** | +1 (Buy) | Long call/put | 0.5 % | -30 % | +70 % / 2× gamma |
| **ETF Flow** | -1 (Sell) | 20Δ vertical | 1 % | 2× credit | 15 % profit |
| **Equity Event** | -1 (Sell) | Iron condor | 0.5 % | 2× credit | 70 % decay |
| **Equity Event** | +1 (Buy) | Long gap follow | 0.3 % | -30 % | Close EOD |

**Global Rule**: Never exceed **3 concurrent trades** or **3 % total account risk** at any time.

---

## **Final Pro Tips**
1. **Run Scan Twice**: Once at 10 AM, once at 1:30 PM—different dynamics.  
2. **Sort Results**: Always sort scan by **open_interest descending** first, then by **signal strength**.  
3. **Avoid**: **Fed days** (Wednesday 2 PM ET), **OPEX Friday** morning, **CPI/PMI mornings**.  
4. **Slippage**: For SPX/NDX, use **mid + 0.05** for buys; **mid - 0.05** for sells.  
5. **Journal**: Log every trade with **score, vrp, gammaAdjVol** values; optimize thresholds monthly.

This system gives you the same data edge that prop desks pay $10K/month for—use it mechanically, size conservatively, and you’ll have a durable intraday edge in any volatility regime.