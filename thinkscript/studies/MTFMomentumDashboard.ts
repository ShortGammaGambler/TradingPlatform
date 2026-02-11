#####################################################################
# MULTI-TIMEFRAME MOMENTUM DASHBOARD
# 5 Timeframe Confluence Scoring System
# Built for: Travis @ Trav's Trader Lounge
#
# CONCEPT:
# Score momentum across 5 timeframes (1m, 5m, 15m, 1h, Daily)
# When all align = high probability setup
# Confluence score: 0-100
#
# SCORING:
# - Each timeframe: 20 points max
# - EMA alignment: 10 points
# - RSI confirmation: 5 points
# - MACD confirmation: 5 points
#
# USAGE:
# - Score > 80: Strong bullish confluence
# - Score > 60: Moderate bullish
# - Score 40-60: Mixed/choppy
# - Score < 40: Bearish leaning
# - Score < 20: Strong bearish confluence
#####################################################################

declare lower;

# INPUTS
input showLabels = yes;
input alertThreshold = 80;

# ============================================
# CURRENT TIMEFRAME ANALYSIS
# ============================================

def ema8 = ExpAverage(close, 8);
def ema21 = ExpAverage(close, 21);
def ema50 = ExpAverage(close, 50);

def rsi = RSI(14);
def macdValue = MACD().Value;
def macdSignal = MACD().Avg;
def macdHist = macdValue - macdSignal;

# EMA Score (0-10)
def emaScore = (if ema8 > ema21 then 5 else 0) +
               (if ema21 > ema50 then 3 else 0) +
               (if close > ema8 then 2 else 0);

# RSI Score (0-5)
def rsiScore = if rsi > 60 then 5
               else if rsi > 50 then 3
               else if rsi < 40 then 0
               else 2;

# MACD Score (0-5)
def macdScore = (if macdValue > macdSignal then 3 else 0) +
                (if macdHist > macdHist[1] then 2 else 0);

def currentTFScore = emaScore + rsiScore + macdScore;

# ============================================
# SIMULATED HIGHER TIMEFRAMES
# (Using longer lookbacks to approximate)
# ============================================

# 5-minute approximation (5x current)
def ema8_5m = ExpAverage(close, 40);
def ema21_5m = ExpAverage(close, 105);
def tf5mScore = (if ema8_5m > ema21_5m then 10 else 0) +
                (if close > ema8_5m then 5 else 0) +
                (if RSI(70) > 50 then 5 else 0);

# 15-minute approximation (15x current)
def ema8_15m = ExpAverage(close, 120);
def ema21_15m = ExpAverage(close, 315);
def tf15mScore = (if ema8_15m > ema21_15m then 10 else 0) +
                 (if close > ema8_15m then 5 else 0) +
                 (if RSI(210) > 50 then 5 else 0);

# Hourly approximation (using daily SMA relationships)
def sma20 = SimpleMovingAvg(close, 20);
def sma50 = SimpleMovingAvg(close, 50);
def hourlyScore = (if sma20 > sma50 then 10 else 0) +
                  (if close > sma20 then 5 else 0) +
                  (if close > close[20] then 5 else 0);

# Daily approximation
def sma50d = SimpleMovingAvg(close, 50);
def sma200d = SimpleMovingAvg(close, 200);
def dailyScore = (if sma50d > sma200d then 10 else 0) +
                 (if close > sma50d then 5 else 0) +
                 (if close > close[50] then 5 else 0);

# ============================================
# TOTAL CONFLUENCE SCORE
# ============================================

def totalScore = currentTFScore + tf5mScore + tf15mScore + hourlyScore + dailyScore;

# Normalize to 0-100
def normalizedScore = (totalScore / 100) * 100;

# ============================================
# SIGNAL CLASSIFICATION
# ============================================

def signal = if normalizedScore >= 80 then 2        # Strong bullish
             else if normalizedScore >= 60 then 1  # Bullish
             else if normalizedScore <= 20 then -2 # Strong bearish
             else if normalizedScore <= 40 then -1 # Bearish
             else 0;                               # Neutral

# ============================================
# PLOTS
# ============================================

plot Score = normalizedScore;
Score.SetDefaultColor(Color.WHITE);
Score.SetLineWeight(2);

plot BullThreshold = 60;
BullThreshold.SetDefaultColor(Color.DARK_GREEN);
BullThreshold.SetStyle(Curve.SHORT_DASH);

plot BearThreshold = 40;
BearThreshold.SetDefaultColor(Color.DARK_RED);
BearThreshold.SetStyle(Curve.SHORT_DASH);

plot StrongBull = 80;
StrongBull.SetDefaultColor(Color.GREEN);
StrongBull.SetStyle(Curve.SHORT_DASH);

plot StrongBear = 20;
StrongBear.SetDefaultColor(Color.RED);
StrongBear.SetStyle(Curve.SHORT_DASH);

# Color the score line
Score.AssignValueColor(
    if normalizedScore >= 80 then Color.GREEN
    else if normalizedScore >= 60 then Color.DARK_GREEN
    else if normalizedScore <= 20 then Color.RED
    else if normalizedScore <= 40 then Color.DARK_RED
    else Color.YELLOW
);

# ============================================
# LABELS
# ============================================

AddLabel(showLabels,
    "MTF Score: " + Round(normalizedScore, 0) + "/100",
    if normalizedScore >= 80 then Color.GREEN
    else if normalizedScore >= 60 then Color.DARK_GREEN
    else if normalizedScore <= 20 then Color.RED
    else if normalizedScore <= 40 then Color.DARK_RED
    else Color.YELLOW
);

AddLabel(showLabels,
    if signal == 2 then "STRONG BULLISH CONFLUENCE"
    else if signal == 1 then "BULLISH CONFLUENCE"
    else if signal == -2 then "STRONG BEARISH CONFLUENCE"
    else if signal == -1 then "BEARISH CONFLUENCE"
    else "MIXED / CHOPPY",
    if signal >= 1 then Color.GREEN
    else if signal <= -1 then Color.RED
    else Color.YELLOW
);

# Component scores
AddLabel(showLabels,
    "Current TF: " + Round(currentTFScore, 0),
    if currentTFScore >= 15 then Color.GREEN
    else if currentTFScore <= 5 then Color.RED
    else Color.GRAY
);

# ============================================
# CLOUD FILL
# ============================================

AddCloud(Score, BullThreshold, Color.DARK_GREEN, Color.DARK_RED);

# ============================================
# ALERTS
# ============================================

Alert(normalizedScore crosses above alertThreshold, "MTF Score crossed above " + alertThreshold, Alert.BAR, Sound.Ding);
Alert(normalizedScore crosses below (100 - alertThreshold), "MTF Score crossed below " + (100 - alertThreshold), Alert.BAR, Sound.Ring);
Alert(signal[1] <= 0 and signal == 2, "Strong Bullish Confluence!", Alert.BAR, Sound.Chimes);
Alert(signal[1] >= 0 and signal == -2, "Strong Bearish Confluence!", Alert.BAR, Sound.Bell);
