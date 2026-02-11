# Power Hour Strategy Playbook

## Situation 1: Stock Approaching Round Number (Most Common)

### AAPL Example: $148.73 → targeting $150.00
**Scanner Shows**: Score 11, Volume 2.1x, 1.27 points to round number

**Strategy Decision Tree**:

**If Bullish Momentum (RSI >52, green candles)**:
- **Conservative**: Buy $149 calls (0.6 delta, safer)
- **Balanced**: Buy $150 calls (0.4 delta, at target)  
- **Aggressive**: Buy $151 calls (0.2 delta, breakout play)

**Position Sizing**:
- Score 11 = 1.5% max risk
- $10K account = $150 max risk
- If $150 calls cost $0.50, buy 3 contracts ($150 risk)

**Exit Plan**:
- Target 1: 50% profit (sell half at $0.75)
- Target 2: At $150.00 or 3:58 PM
- Stop: If drops below $148.50 or volume dies

### TSLA Example: $251.20 → targeting $250.00 (Bearish Pin)
**Scanner Shows**: Score 10, Volume 1.9x, RSI 38, rejecting round number

**Strategy**:
- **Primary**: Buy $250 puts (0.4 delta)
- **Alternative**: Buy $249 puts (0.6 delta, deeper target)
- **Aggressive**: $251 puts (0.2 delta, betting on breakdown)

## Situation 2: Breakout Above Round Number

### NVDA Example: Breaks above $500.00 at 3:35 PM
**Scanner Shows**: Score 12, Volume 3.2x, clean break with volume

**Call Strategy**:
- **Momentum Play**: Buy $502 calls (riding the wave)
- **Conservative**: Buy $500 calls (already ITM, safer)
- **Swing**: Buy $505 calls (betting on continued momentum)

**Entry Rules**:
- Wait for 2-minute confirmation above $500
- Volume must stay elevated
- No major resistance until $510

**Risk Management**:
- Stop if falls back below $500.00
- Target: Next round number ($510) or 50% profit

## Situation 3: Rejection at Round Number

### SPY Example: Hits $450.00 but immediately reverses
**Scanner Shows**: Score 9, Volume spike, bearish reversal candle

**Put Strategy**:
- **Primary**: Buy $450 puts (right at rejection level)
- **Target**: $448 (previous support/round number)
- **Aggressive**: $449 puts (tighter stop, higher probability)

**Confirmation Needed**:
- Reversal candle with upper wick
- Volume on the rejection
- RSI showing overbought (>65)

## Strike Selection Formula

### Distance-Based Selection
**Stock within 1% of round number**:
- Buy strikes AT the round number (maximum gamma)

**Stock 1-2% from round number**:
- Buy strikes 1 level closer to current price (higher delta)

**Stock >2% from round number**:
- Usually avoid - too far for gamma effects

### Time-Based Adjustments
**3:30-3:45 PM**: Can use slightly OTM strikes (more time)
**3:45-3:55 PM**: Focus on ATM/ITM strikes (less time risk)  
**3:55-4:00 PM**: Only ITM strikes (gamma explosion)

## Position Sizing by Scanner Score

### Score 12+ (Rare, High Conviction)
- **Risk**: 2-3% of account
- **Contracts**: Calculate based on option price
- **Example**: $10K account, $0.75 option = 4 contracts max

### Score 10-11 (Good Setup)  
- **Risk**: 1-2% of account
- **Example**: $10K account, $0.50 option = 3 contracts max

### Score 8-9 (Marginal Setup)
- **Risk**: 0.5-1% of account  
- **Example**: $10K account, $0.25 option = 2 contracts max

## Real-Time Decision Examples

### Example 1: 3:32 PM - MSFT at $419.80
**Scanner**: Score 10, targeting $420
**Volume**: 1.8x average
**Strategy**: Buy $420 calls (0.3 delta)
**Risk**: $150 on 3 contracts at $0.50
**Target**: 50% profit or $420 touch

### Example 2: 3:41 PM - QQQ at $383.30  
**Scanner**: Score 11, rejecting $385
**Volume**: 2.3x average, bearish candles
**Strategy**: Buy $383 puts (0.4 delta)
**Risk**: $200 on 4 contracts at $0.50
**Target**: $380 or 50% profit

### Example 3: 3:50 PM - AMD at $139.60
**Scanner**: Score 9, approaching $140
**Volume**: 1.6x average but fading
**Decision**: SKIP - volume not confirming, too close to close

## Exit Strategy Matrix

### Profit Taking
- **50% Profit**: Always take half off
- **Round Number Hit**: Consider full exit
- **100% Profit**: Take 75% off, let 25% run

### Stop Losses
- **Volume Death**: Exit immediately if volume drops 50%
- **Score Deterioration**: Exit if scanner score drops below 6
- **Time Stop**: All positions closed by 3:58 PM

### Special Situations
- **3:58 PM**: Close everything regardless of P&L
- **Halt/News**: Exit immediately on resumption  
- **VIX Spike >10%**: Reduce all position sizes by half

## Common Mistakes & Solutions

### ❌ Mistake: Chasing after 3:50 PM
**Solution**: No new positions after 3:50 PM unless Score 12+

### ❌ Mistake: Wrong strike selection
**Solution**: Use the formula - close to round number = strike AT round number

### ❌ Mistake: Ignoring volume confirmation
**Solution**: Volume must stay elevated throughout the trade

### ❌ Mistake: Over-sizing positions
**Solution**: Never risk more than scanner score suggests

## Success Metrics to Track

### Daily Goals
- **Win Rate**: 65%+ for Score 10+ setups
- **Risk/Reward**: Average winner 1.5x average loser
- **Max Trades**: 3 positions per day maximum

### Weekly Calibration
- Which strikes worked best for each setup type?
- What time window had highest success rate?
- Did position sizing match actual risk tolerance?

**Remember**: Power hour is about precision, not frequency. One good setup properly executed beats three marginal setups every time.
