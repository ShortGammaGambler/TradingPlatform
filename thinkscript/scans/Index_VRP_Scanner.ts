## **PART 1: SPX/NDX Index Volatility Arbitrage Scanner**
*Captures variance risk premium (VRP) and term-structure dislocations in cash indices.*

### **Script: `Index_VRP_Scanner`**
```thinkscript
# SPX/NDX Index Volatility Arbitrage Scanner
# Use on: Options scan (Weeklys + Monthlys), Underlying = SPX, NDX

# ========== INPUTS ==========
input minVRP          = 15.0;      # VRP >= 15% (IV vs HV gap)
input maxSkew         = 1.15;      # Put/Call IV ratio <= 1.15 (calls rich) or >= 1.35 (puts rich)
input minDTE          = 0;         # include 0-DTE
input maxDTE          = 7;         # focus on front week
input minOpenInterest = 1000;      # deep liquidity
input minBlockFlow    = 500;       # block volume today
# ============================

def underlying = GetUnderlyingSymbol();
def isIndex = underlying == "SPX" or underlying == "NDX";
def dte = GetDaysToExpiration();
def iv30 = SeriesVolatility(GetUnderlyingSymbol());
def hv20 = HistoricalVolatility(length = 20);
def vrp = 100 * (iv30 - hv20) / hv20;

# VRP filter
def vrpOk = vrp >= minVRP;

# Term structure: front month IV > back month IV = "contango"
def backMonthIV = SeriesVolatility(GetUnderlyingSymbol(), AggregationPeriod.MONTH, 45);
def termOk = iv30 > backMonthIV;

# Skew: ATM put IV / ATM call IV
def atmPutIV = SeriesVolatility(GetUnderlyingSymbol(), AggregationPeriod.DAY, 0, OptionClass.PUT);
def atmCallIV = SeriesVolatility(GetUnderlyingSymbol(), AggregationPeriod.DAY, 0, OptionClass.CALL);
def skew = atmPutIV / atmCallIV;

# Skew envelope: either calls rich (low skew) or puts rich (high skew) for verticals
def skewOk = skew <= maxSkew or skew >= 1.35;

# Block flow (large-lot orders)
def blockVol = if volume >= minBlockFlow then volume else 0;
def blockOk = blockVol > 0;

# Composite
def setup = isIndex and dte >= minDTE and dte <= maxDTE and vrpOk and termOk and skewOk and open_interest >= minOpenInterest and blockOk;

# Signal: +1 = sell premium (rich), -1 = buy premium (cheap)
def signal = if setup and vrp >= 20 then 1 else if setup and vrp < 10 then -1 else 0;

plot IndexVRPTrade = signal;
```

---

### **How to Use It**
1. **Setup**:  
   - Open **TOS → Scan → Add Filter → Study → Custom → ThinkScript**  
   - Paste code, save as "Index_VRP_Scanner"  
   - Set **Scan in**: **Option**  
   - Enable **Weeklys** and **Monthlys**  
   - Under **Contracts**: manually type `SPX, NDX` in the symbol box

2. **Time to Run**:  
   **9:45 AM – 10:15 AM ET** (after opening skew settles)  
   **Avoid**: FOMC days, CPI release mornings, monthly OPEX (skew collapses)

3. **Result Interpretation**:  
   - **+1 (Sell Premium)**: Execute **iron condor** or **strangle** (sell 15Δ put + 15Δ call, same DTE).  
     - **Width**: 50-100 points wide for SPX, 200-400 for NDX.  
     - **Exit**: Buy back at 25 % max credit or by 2 PM ET.  
   - **-1 (Buy Premium)**: Execute **straddle** (buy ATM put + call).  
     - **Risk**: 0.3 % of account per straddle.  
     - **Exit**: +60 % profit or -30 % stop.

4. **Risk Management**:  
   - **Max loss per trade**: 1 % of account (selling) / 0.5 % (buying).  
   - **No overnight holds** for 0-3 DTE setups.

---
