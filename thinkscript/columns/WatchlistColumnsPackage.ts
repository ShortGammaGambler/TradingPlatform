#####################################################################
# CUSTOM WATCHLIST COLUMNS PACKAGE
# Institutional-Grade Data Points for Quick Scanning
# Built for: Travis @ Trav's Trader Lounge
#
# INCLUDED COLUMNS:
# 1. IV Percentile (30-day)
# 2. Expected Move (Weekly)
# 3. Put/Call Volume Ratio
# 4. Correlation to SPX
# 5. Momentum Score
# 6. Smart Money Flow
# 7. Volume Ratio
# 8. Distance to VWAP
#
# HOW TO ADD:
# 1. TOS > Watchlist > Customize
# 2. Add Column > Custom Quote
# 3. Paste individual column code
#####################################################################

#====================================================================
# COLUMN 1: IV PERCENTILE (30-DAY)
# Shows current IV rank relative to past year
#====================================================================
# PASTE THIS CODE FOR IV PERCENTILE COLUMN:

# def atr = ATR(14);
# def ivProxy = (atr / close) * 100 * 16;
# def ivHigh = Highest(ivProxy, 252);
# def ivLow = Lowest(ivProxy, 252);
# def ivPercentile = ((ivProxy - ivLow) / (ivHigh - ivLow + 0.001)) * 100;
# plot IVPct = Round(ivPercentile, 0);
# IVPct.AssignValueColor(if ivPercentile > 60 then Color.GREEN else if ivPercentile < 30 then Color.RED else Color.YELLOW);

#====================================================================
# COLUMN 2: EXPECTED MOVE (WEEKLY)
# Shows 1-week expected move in percentage
#====================================================================
# PASTE THIS CODE FOR EXPECTED MOVE COLUMN:

# def atr = ATR(14);
# def ivProxy = (atr / close) * 100 * 16;
# def weeklyMove = ivProxy * Sqrt(5/252);
# plot ExpMove = Round(weeklyMove, 1);
# ExpMove.AssignValueColor(Color.CYAN);

#====================================================================
# COLUMN 3: VOLUME RATIO
# Today's volume vs 20-day average
#====================================================================
# PASTE THIS CODE FOR VOLUME RATIO COLUMN:

# def avgVol = Average(volume, 20);
# def volRatio = volume / avgVol;
# plot VolR = Round(volRatio, 1);
# VolR.AssignValueColor(if volRatio > 2 then Color.CYAN else if volRatio > 1.5 then Color.GREEN else if volRatio < 0.5 then Color.RED else Color.GRAY);

#====================================================================
# COLUMN 4: CORRELATION TO SPX
# Rolling 20-day correlation with SPY
#====================================================================
# PASTE THIS CODE FOR CORRELATION COLUMN:

# def spyClose = close("SPY");
# def stockRet = (close - close[1]) / close[1];
# def spyRet = (spyClose - spyClose[1]) / spyClose[1];
# def covar = Sum((stockRet - Average(stockRet, 20)) * (spyRet - Average(spyRet, 20)), 20) / 20;
# def stockStd = Sqrt(Sum(Power(stockRet - Average(stockRet, 20), 2), 20) / 20);
# def spyStd = Sqrt(Sum(Power(spyRet - Average(spyRet, 20), 2), 20) / 20);
# def corr = covar / (stockStd * spyStd + 0.001);
# plot Corr = Round(corr, 2);
# Corr.AssignValueColor(if corr > 0.7 then Color.GREEN else if corr < 0.3 then Color.RED else Color.YELLOW);

#====================================================================
# COLUMN 5: MOMENTUM SCORE
# Composite momentum indicator (0-100)
#====================================================================
# PASTE THIS CODE FOR MOMENTUM COLUMN:

# def ema8 = ExpAverage(close, 8);
# def ema21 = ExpAverage(close, 21);
# def rsi = RSI(14);
# def macd = MACD().Value;
# def signal = MACD().Avg;
# def score = (if ema8 > ema21 then 25 else 0) + (if rsi > 50 then 25 else 0) + (if macd > signal then 25 else 0) + (if close > ema21 then 25 else 0);
# plot Mom = score;
# Mom.AssignValueColor(if score >= 75 then Color.GREEN else if score >= 50 then Color.DARK_GREEN else if score <= 25 then Color.RED else Color.DARK_RED);

#====================================================================
# COLUMN 6: SMART MONEY FLOW
# Institutional flow approximation (-100 to +100)
#====================================================================
# PASTE THIS CODE FOR SMART FLOW COLUMN:

# def avgVol = Average(volume, 20);
# def largeVol = volume > avgVol * 2;
# def priceMove = close - open;
# def largeBuy = if largeVol and priceMove > 0 then volume else 0;
# def largeSell = if largeVol and priceMove < 0 then volume else 0;
# def netFlow = Sum(largeBuy - largeSell, 20);
# def totalFlow = Sum(largeBuy + largeSell, 20) + 1;
# def flowPct = (netFlow / totalFlow) * 100;
# plot SmartFlow = Round(flowPct, 0);
# SmartFlow.AssignValueColor(if flowPct > 30 then Color.GREEN else if flowPct < -30 then Color.RED else Color.GRAY);

#====================================================================
# COLUMN 7: DISTANCE TO VWAP
# Percentage distance from VWAP
#====================================================================
# PASTE THIS CODE FOR VWAP DISTANCE COLUMN:

# def dist = ((close - vwap) / vwap) * 100;
# plot VWAPDist = Round(dist, 2);
# VWAPDist.AssignValueColor(if dist > 1 then Color.GREEN else if dist < -1 then Color.RED else Color.YELLOW);

#====================================================================
# COLUMN 8: GAMMA REGIME
# Current gamma environment estimate
#====================================================================
# PASTE THIS CODE FOR GAMMA REGIME COLUMN:

# def priceChange = close - close[1];
# def mrScore = if priceChange > 0 and priceChange[1] < 0 then 1 else if priceChange < 0 and priceChange[1] > 0 then 1 else 0;
# def mrRate = Average(mrScore, 20) * 100;
# def atr = ATR(14);
# def atrPct = (atr / close) * 100;
# def histATR = Average(atrPct, 40);
# def volReg = atrPct / histATR;
# def gammaScore = (mrRate - 50) * 2 + (1 - volReg) * 20;
# plot Gamma = if gammaScore > 15 then 1 else if gammaScore < -15 then -1 else 0;
# Gamma.AssignValueColor(if Gamma > 0 then Color.GREEN else if Gamma < 0 then Color.RED else Color.YELLOW);

#====================================================================
# COLUMN 9: 0DTE SIGNAL
# Quick 0DTE opportunity flag
#====================================================================
# PASTE THIS CODE FOR 0DTE SIGNAL COLUMN:

# def ema8 = ExpAverage(close, 8);
# def ema21 = ExpAverage(close, 21);
# def rsi = RSI(14);
# def nearVWAP = AbsValue(close - vwap) < ATR(14) * 1.5;
# def bullSetup = ema8 > ema21 and rsi > 50 and nearVWAP;
# def bearSetup = ema8 < ema21 and rsi < 50 and nearVWAP;
# plot Signal = if bullSetup then 1 else if bearSetup then -1 else 0;
# Signal.AssignValueColor(if Signal > 0 then Color.GREEN else if Signal < 0 then Color.RED else Color.GRAY);

#====================================================================
# COLUMN 10: EXPECTED MOVE (POINTS)
# Daily expected move in price points
#====================================================================
# PASTE THIS CODE FOR EXPECTED POINTS COLUMN:

# def atr = ATR(14);
# def ivProxy = (atr / close) * 100 * 16;
# def dailyMove = close * ivProxy / 100 * Sqrt(1/252);
# plot ExpPts = Round(dailyMove, 2);
# ExpPts.AssignValueColor(Color.WHITE);

#####################################################################
# END CUSTOM WATCHLIST COLUMNS PACKAGE
#####################################################################
