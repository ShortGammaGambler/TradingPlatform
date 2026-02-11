#####################################################################
# GAMMA REGIME INDICATOR
# Approximates dealer gamma positioning from price action
# Built for: Travis @ Trav's Trader Lounge
#
# CONCEPT:
# Positive gamma = dealers hedge by buying dips, selling rips
# Result: Mean reversion, compressed volatility
#
# Negative gamma = dealers hedge by selling dips, buying rips
# Result: Momentum amplification, expanded volatility
#
# This indicator approximates gamma regime from:
# 1. Mean reversion rate (how often reversals occur)
# 2. Volatility expansion/contraction
# 3. Price behavior at key levels
#
# USAGE:
# - Green = Positive gamma (fade extremes, sell premium)
# - Yellow = Neutral
# - Red = Negative gamma (follow momentum, buy protection)
#####################################################################

declare lower;

# INPUTS
input lookbackPeriod = 20;       # Period for analysis
input showLabels = yes;
input showHistogram = yes;

# MEAN REVERSION ANALYSIS
# Count direction changes (higher = more mean reversion = positive gamma)
def priceChange = close - close[1];
def directionChange = if priceChange > 0 and priceChange[1] < 0 then 1
                      else if priceChange < 0 and priceChange[1] > 0 then 1
                      else 0;
def meanReversionRate = Sum(directionChange, lookbackPeriod) / lookbackPeriod * 100;

# VOLATILITY REGIME
# Compare current ATR to historical ATR
def atr = ATR(14);
def atrPct = (atr / close) * 100;
def historicalATR = Average(atrPct, lookbackPeriod * 2);
def volRatio = atrPct / historicalATR;

# MOMENTUM PERSISTENCE
# How often does momentum continue vs reverse
def momentumContinue = if priceChange > 0 and priceChange[1] > 0 then 1
                       else if priceChange < 0 and priceChange[1] < 0 then 1
                       else 0;
def momentumRate = Sum(momentumContinue, lookbackPeriod) / lookbackPeriod * 100;

# GAMMA SCORE CALCULATION
# Positive score = positive gamma environment
# Negative score = negative gamma environment

def gammaScore = (meanReversionRate - 50) * 2    # Mean reversion contribution
                 + (1 - volRatio) * 30            # Low vol = positive gamma
                 - (momentumRate - 50) * 1.5;     # High momentum = negative gamma

# Normalize to -100 to +100
def normalizedScore = Max(-100, Min(100, gammaScore));

# REGIME CLASSIFICATION
def regime = if normalizedScore > 25 then 2      # Strong positive
             else if normalizedScore > 5 then 1  # Mild positive
             else if normalizedScore < -25 then -2  # Strong negative
             else if normalizedScore < -5 then -1   # Mild negative
             else 0;                              # Neutral

# PLOTS
plot GammaScore = normalizedScore;
GammaScore.SetDefaultColor(Color.WHITE);
GammaScore.SetLineWeight(2);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(Color.GRAY);
ZeroLine.SetStyle(Curve.SHORT_DASH);

plot PositiveThreshold = 25;
PositiveThreshold.SetDefaultColor(Color.DARK_GREEN);
PositiveThreshold.SetStyle(Curve.SHORT_DASH);

plot NegativeThreshold = -25;
NegativeThreshold.SetDefaultColor(Color.DARK_RED);
NegativeThreshold.SetStyle(Curve.SHORT_DASH);

# COLOR THE SCORE LINE
GammaScore.AssignValueColor(
    if normalizedScore > 25 then Color.GREEN
    else if normalizedScore > 5 then Color.DARK_GREEN
    else if normalizedScore < -25 then Color.RED
    else if normalizedScore < -5 then Color.DARK_RED
    else Color.YELLOW
);

# HISTOGRAM (optional)
plot Histogram = if showHistogram then normalizedScore else Double.NaN;
Histogram.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Histogram.AssignValueColor(
    if normalizedScore > 25 then Color.GREEN
    else if normalizedScore > 5 then Color.DARK_GREEN
    else if normalizedScore < -25 then Color.RED
    else if normalizedScore < -5 then Color.DARK_RED
    else Color.YELLOW
);

# LABELS
AddLabel(showLabels,
    if regime == 2 then "GAMMA: STRONG POSITIVE"
    else if regime == 1 then "GAMMA: POSITIVE"
    else if regime == -2 then "GAMMA: STRONG NEGATIVE"
    else if regime == -1 then "GAMMA: NEGATIVE"
    else "GAMMA: NEUTRAL",
    if regime >= 1 then Color.GREEN
    else if regime <= -1 then Color.RED
    else Color.YELLOW
);

AddLabel(showLabels,
    "Score: " + Round(normalizedScore, 1),
    Color.WHITE
);

# STRATEGY HINTS
AddLabel(showLabels and regime >= 1,
    "Strategy: Fade moves, Sell premium",
    Color.CYAN
);

AddLabel(showLabels and regime <= -1,
    "Strategy: Follow momentum, Buy protection",
    Color.MAGENTA
);

# ALERTS
Alert(regime[1] != 2 and regime == 2, "Gamma turned STRONG POSITIVE", Alert.BAR, Sound.Ding);
Alert(regime[1] != -2 and regime == -2, "Gamma turned STRONG NEGATIVE", Alert.BAR, Sound.Ring);
Alert(regime[1] >= 1 and regime <= -1, "Gamma flipped to NEGATIVE", Alert.BAR, Sound.Bell);
Alert(regime[1] <= -1 and regime >= 1, "Gamma flipped to POSITIVE", Alert.BAR, Sound.Chimes);
