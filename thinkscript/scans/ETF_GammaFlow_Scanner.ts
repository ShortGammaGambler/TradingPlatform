## **PART 2: SPY/QQQ ETF Flow & Gamma Squeeze Scanner**
*Identifies where dealer gamma positioning + retail flow creates explosive moves.*

### **Script: `ETF_GammaFlow_Scanner`**
```thinkscript
# SPY/QQQ Gamma-Weighted Flow Scanner
# Use on: Options scan (Weeklys), Underlying = SPY, QQQ

# ========== INPUTS ==========
input minGammaAdjVol = 50000;    # Gamma * Volume * OI threshold
input minGamma       = 0.003;    # Dealer gamma flip threshold
input maxSpreadPct   = 3.0;      # Tight spread only
input minOI          = 2000;     # Avoid dead contracts
input vwapDev        = 0.002;    # Price > VWAP * 0.2% (momentum)
# ============================

def underlying = GetUnderlyingSymbol();
def isETF = underlying == "SPY" or underlying == "QQQ";
def dte = GetDaysToExpiration();
def price = close;

# VWAP deviation
def vwapVal = VWAP();
def vwapOk = price > vwapVal * (1 + vwapDev);

# Gamma-adjusted volume (dealer hedge pressure)
def gamma = Gamma();
def gammaAdjVol = volume * gamma * open_interest;
def gammaOk = gammaAdjVol >= minGammaAdjVol and gamma >= minGamma;

# Spread & liquidity
def mid = (bid + ask) / 2;
def spreadPct = 100 * (ask - bid) / mid;
def spreadOk = spreadPct <= maxSpreadPct and bid >= 0.10;

# OTM only (no intrinsic noise)
def strike = GetStrike();
def otm = if GetSymbolPart(1) == "C" then strike > price else strike < price;

# Composite
def setup = isETF and dte <= 7 and dte >= 0 and vwapOk and gammaOk and spreadOk and otm and open_interest >= minOI;

# Signal: +1 = buy (gamma squeeze building), -1 = sell (gamma ceiling)
def signal = if setup and gammaAdjVol > 2 * minGammaAdjVol then 1 else if setup and gammaAdjVol < minGammaAdjVol then -1 else 0;

plot ETFSignal = signal;
```

---

### **How to Use It**
1. **Setup**:  
   - Same as above, but **Scan in**: **Option** with **Weeklys** only  
   - Under **Contracts**: type `SPY, QQQ`

2. **Time to Run**:  
   **10:30 AM – 11:30 AM ET** (after initial hedge rebalancing)  
   **Re-run**: **1:30 PM ET** (lunch fade reversals)

3. **Result Interpretation**:  
   - **+1 (Buy)**: Single-leg **long call** (if QQQ > VWAP) or **long put** (if QQQ < VWAP).  
     - **Target**: 1-2 % move in underlying.  
     - **Exit**: Scale out 50 % at +40 %, rest at +80 % or trailing stop.  
   - **-1 (Sell)**: **Credit spread** against the squeeze (e.g., if gamma shows call-hedge ceiling, sell 20Δ call vertical).  
     - **Width**: $1-2 wide for SPY, $2-5 for QQQ.  
     - **Exit**: Buy back at 15 % credit.

4. **Risk Management**:  
   - **Long**: 0.5 % account risk per contract.  
   - **Short**: 1 % account risk per spread; never more than 3 concurrent shorts.

---
