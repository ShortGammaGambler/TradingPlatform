## **PART 3: Individual Equity Event-Driven & Momentum Scanner**
*Finds single-name setups with earnings catalyst + vol mispricing.*

### **Script: `Equity_EventVol_Scanner`**
```thinkscript
# Equity Event-Driven Vol Scanner
# Use on: Options scan (Weeklys + Monthlys), Universe = S&P 500

# ========== INPUTS ==========
input minRevDeviation = 15.0;    # IV % rank vs 52-week
input maxHistGap      = 5;       # Days since last earnings > 5
importance            = {default high, medium, low};  # Earnings importance
input minMarketCap    = 10000;   # $10B+ (large cap only)
input minDailyVol     = 1000000; # 1M shares/day
input minOptionsVol   = 500;     # contracts today
# ============================

# Earnings filter
def earningsGap = DaysFromLastEarnings();
def hasEarningsSoon = HasEarnings(EarningTime.AFTER_MARKET) or HasEarnings(EarningTime.BEFORE_MARKET);
def earningsOk = earningsGap >= maxHistGap and hasEarningsSoon;

# IV rank vs historical
def ivRank = IVPercentile();
def ivOk = ivRank >= minRevDeviation;

# Market cap & liquidity
def cap = MarketCap();
def volumeOk = volume >= minDailyVol and volume(period = AggregationPeriod.DAY) >= minOptionsVol;

# Composite
def setup = earningsOk and ivOk and cap >= minMarketCap and volumeOk;

# Signal: -1 = sell pre-earnings vol, +1 = buy post-earnings breakouts
def signal = if setup and !hasEarningsSoon then 1 else if setup and hasEarningsSoon then -1 else 0;

plot EquitySignal = signal;
```

---

### **How to Use It**
1. **Setup**:  
   - **Scan in**: **Option**  
   - **Universe**: **S&P 500** (or any custom list)  
   - Enable **Weeklys + Monthlys**

2. **Time to Run**:  
   **3:50 PM ET** (pre-earnings vol crush entry)  
   **Next day 10:00 AM ET** (post-earnings momentum continuation)

3. **Result Interpretation**:  
   - **-1 (Sell Pre-Earnings)**: **Iron condor** or **strangle** 1-2 days before earnings, exit after the print.  
     - **Width**: 10-15 % OTM strikes.  
     - **Target**: 70 % of premium decay by next morning.  
   - **+1 (Buy Post-Earnings)**: **Long call/put** in direction of earnings gap > 5 %.  
     - **Filter**: Only if gap is *not* faded by 10 AM.  
     - **Stop**: Low of the 5-min opening range.

4. **Risk Management**:  
   - **Pre-earnings short**: 0.5 % account risk per spread; never hold through the announcement.  
   - **Post-earnings long**: 0.3 % account risk; exit by day end.

---
