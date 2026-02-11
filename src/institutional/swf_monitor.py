"""
SOVEREIGN & MACRO MONITOR
Fed Balance Sheet and Sovereign Wealth Fund Tracking
Built for: Travis @ Trav's Trader Lounge

This module tracks:
1. Fed Balance Sheet - QT/QE pace, liquidity conditions
2. Sovereign Wealth Funds - Major SWF flows
3. Macro Liquidity - Global liquidity indicators

Fed balance sheet is THE most important macro variable.
When Fed adds liquidity = risk on
When Fed drains liquidity = risk off
"""

import requests
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FedBalanceSheetData:
    """Fed balance sheet data point"""
    date: date
    total_assets: float           # Billions
    treasuries: float             # Billions
    mbs: float                    # Billions (Mortgage-backed securities)
    reserves: float               # Billions
    rrp: float                    # Reverse repo (billions)
    tga: float                    # Treasury General Account (billions)

    @property
    def net_liquidity(self) -> float:
        """Net liquidity = Assets - RRP - TGA"""
        return self.total_assets - self.rrp - self.tga


@dataclass
class SovereignFlow:
    """Sovereign wealth fund flow data"""
    fund_name: str
    country: str
    aum_billions: float
    monthly_flow_billions: float
    allocation_equities_pct: float
    allocation_bonds_pct: float
    allocation_alternatives_pct: float
    trend: str                    # INCREASING, DECREASING, STABLE


class FedBalanceSheet:
    """
    Track Federal Reserve balance sheet.

    Data from FRED (Federal Reserve Economic Data):
    - WALCL: Total Assets
    - TREAST: Treasury Holdings
    - WSHOMCB: MBS Holdings
    - WRESBAL: Reserve Balances
    - RRPONTSYD: Overnight Reverse Repo
    - WTREGEN: Treasury General Account

    Net Liquidity = Total Assets - RRP - TGA
    This is what matters for risk assets.
    """

    FRED_BASE_URL = "https://api.stlouisfed.org/fred"

    # FRED series IDs
    SERIES = {
        "total_assets": "WALCL",
        "treasuries": "TREAST",
        "mbs": "WSHOMCB",
        "reserves": "WRESBAL",
        "rrp": "RRPONTSYD",
        "tga": "WTREGEN"
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._cache: Dict[str, FedBalanceSheetData] = {}

        logger.info("Fed Balance Sheet tracker initialized")

    def get_current_data(self) -> FedBalanceSheetData:
        """Get latest Fed balance sheet data"""
        if self.api_key:
            return self._fetch_fred_data()
        else:
            return self._mock_data()

    def _fetch_fred_data(self) -> FedBalanceSheetData:
        """Fetch data from FRED API"""
        data = {}

        for name, series_id in self.SERIES.items():
            try:
                url = f"{self.FRED_BASE_URL}/series/observations"
                params = {
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1
                }
                response = requests.get(url, params=params)
                response.raise_for_status()

                obs = response.json().get("observations", [])
                if obs:
                    value = float(obs[0].get("value", 0))
                    # Convert to billions if needed
                    if name in ["total_assets", "treasuries", "mbs", "reserves"]:
                        value = value / 1000  # FRED reports in millions
                    data[name] = value

            except Exception as e:
                logger.error(f"Failed to fetch {name}: {e}")
                data[name] = 0

        return FedBalanceSheetData(
            date=date.today(),
            total_assets=data.get("total_assets", 0),
            treasuries=data.get("treasuries", 0),
            mbs=data.get("mbs", 0),
            reserves=data.get("reserves", 0),
            rrp=data.get("rrp", 0),
            tga=data.get("tga", 0)
        )

    def _mock_data(self) -> FedBalanceSheetData:
        """Return mock data for testing"""
        return FedBalanceSheetData(
            date=date.today(),
            total_assets=7800,      # $7.8T
            treasuries=4800,        # $4.8T
            mbs=2400,               # $2.4T
            reserves=3200,          # $3.2T
            rrp=500,                # $500B
            tga=750                 # $750B
        )

    def get_qt_pace(self) -> Dict:
        """
        Calculate current QT pace and interpret.

        QT = Quantitative Tightening (Fed selling/letting bonds roll off)
        QE = Quantitative Easing (Fed buying bonds)
        """
        current = self.get_current_data()

        # In production, compare to historical data
        # For now, use mock historical
        one_month_ago = FedBalanceSheetData(
            date=date.today() - timedelta(days=30),
            total_assets=current.total_assets + 50,  # Mock: was $50B higher
            treasuries=current.treasuries + 30,
            mbs=current.mbs + 20,
            reserves=current.reserves,
            rrp=current.rrp - 100,  # RRP decreased
            tga=current.tga + 50
        )

        # Calculate changes
        total_change = current.total_assets - one_month_ago.total_assets
        treasury_change = current.treasuries - one_month_ago.treasuries
        mbs_change = current.mbs - one_month_ago.mbs
        net_liq_change = current.net_liquidity - one_month_ago.net_liquidity

        # Interpret
        if total_change < -60:
            interpretation = "AGGRESSIVE QT - Fed draining liquidity fast"
        elif total_change < -30:
            interpretation = "MODERATE QT - Normal balance sheet reduction"
        elif total_change < 0:
            interpretation = "SLOW QT - Minimal tightening"
        elif total_change == 0:
            interpretation = "PAUSED - No change in balance sheet"
        elif total_change < 50:
            interpretation = "SLOW EXPANSION - Possible intervention"
        else:
            interpretation = "EMERGENCY EXPANSION - Crisis response"

        return {
            "date": current.date.isoformat(),
            "current_balance_sheet_billions": current.total_assets,
            "monthly_total_change_billions": total_change,
            "monthly_treasury_change_billions": treasury_change,
            "monthly_mbs_change_billions": mbs_change,
            "net_liquidity_billions": current.net_liquidity,
            "net_liquidity_change_billions": net_liq_change,
            "rrp_billions": current.rrp,
            "tga_billions": current.tga,
            "interpretation": interpretation,
            "risk_asset_bias": "BULLISH" if net_liq_change > 0 else "BEARISH" if net_liq_change < -50 else "NEUTRAL"
        }


class SWFMonitor:
    """
    Monitor Sovereign Wealth Fund flows.

    Major SWFs:
    - Norway GPFG ($1.4T)
    - China CIC ($1.2T)
    - Abu Dhabi ADIA ($900B)
    - Kuwait KIA ($750B)
    - Singapore GIC ($700B)

    SWFs are the largest, longest-term investors.
    Their moves matter for strategic positioning.
    """

    MAJOR_SWFS = {
        "GPFG": {"name": "Norway Government Pension Fund Global", "country": "Norway", "aum": 1400},
        "CIC": {"name": "China Investment Corporation", "country": "China", "aum": 1200},
        "ADIA": {"name": "Abu Dhabi Investment Authority", "country": "UAE", "aum": 900},
        "KIA": {"name": "Kuwait Investment Authority", "country": "Kuwait", "aum": 750},
        "GIC": {"name": "Singapore GIC", "country": "Singapore", "aum": 700},
        "NBIM": {"name": "Norges Bank Investment Management", "country": "Norway", "aum": 500},
        "QIA": {"name": "Qatar Investment Authority", "country": "Qatar", "aum": 450},
        "HKMA": {"name": "Hong Kong Monetary Authority", "country": "Hong Kong", "aum": 400},
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

        logger.info("SWF Monitor initialized")

    def get_swf_allocations(self) -> List[SovereignFlow]:
        """Get current SWF allocation data"""
        # In production, would fetch from SWFI or similar
        # For now, return mock data

        import random

        flows = []
        for code, info in self.MAJOR_SWFS.items():
            flows.append(SovereignFlow(
                fund_name=info["name"],
                country=info["country"],
                aum_billions=info["aum"],
                monthly_flow_billions=random.uniform(-5, 10),
                allocation_equities_pct=random.uniform(50, 70),
                allocation_bonds_pct=random.uniform(20, 35),
                allocation_alternatives_pct=random.uniform(5, 20),
                trend=random.choice(["INCREASING", "DECREASING", "STABLE"])
            ))

        return flows

    def get_aggregate_flows(self) -> Dict:
        """Get aggregate SWF flow summary"""
        flows = self.get_swf_allocations()

        total_aum = sum(f.aum_billions for f in flows)
        total_monthly_flow = sum(f.monthly_flow_billions for f in flows)
        avg_equity_allocation = sum(f.allocation_equities_pct for f in flows) / len(flows)

        increasing = sum(1 for f in flows if f.trend == "INCREASING")
        decreasing = sum(1 for f in flows if f.trend == "DECREASING")

        if increasing > decreasing * 2:
            trend = "RISK_ON"
        elif decreasing > increasing * 2:
            trend = "RISK_OFF"
        else:
            trend = "MIXED"

        return {
            "total_aum_billions": total_aum,
            "monthly_net_flow_billions": total_monthly_flow,
            "avg_equity_allocation_pct": avg_equity_allocation,
            "funds_increasing": increasing,
            "funds_decreasing": decreasing,
            "aggregate_trend": trend,
            "interpretation": (
                "SWFs net adding to risk assets - long-term bullish" if total_monthly_flow > 10
                else "SWFs net reducing risk - long-term cautious" if total_monthly_flow < -10
                else "SWF flows balanced - no strong signal"
            )
        }


class SovereignMonitor:
    """
    Combined sovereign and macro liquidity monitor.

    Tracks:
    1. Fed balance sheet and QT/QE
    2. SWF flows
    3. Global central bank liquidity (future)
    """

    def __init__(
        self,
        swfi_api_key: Optional[str] = None,
        fred_api_key: Optional[str] = None
    ):
        self.fed = FedBalanceSheet(fred_api_key)
        self.swf = SWFMonitor(swfi_api_key)

        logger.info("Sovereign Monitor initialized")

    def get_liquidity_conditions(self) -> Dict:
        """Get comprehensive liquidity assessment"""
        fed_data = self.fed.get_qt_pace()
        swf_data = self.swf.get_aggregate_flows()

        # Combine signals
        fed_bias = fed_data.get("risk_asset_bias", "NEUTRAL")
        swf_trend = swf_data.get("aggregate_trend", "MIXED")

        if fed_bias == "BULLISH" and swf_trend == "RISK_ON":
            combined = "STRONGLY_SUPPORTIVE"
        elif fed_bias == "BULLISH" or swf_trend == "RISK_ON":
            combined = "SUPPORTIVE"
        elif fed_bias == "BEARISH" and swf_trend == "RISK_OFF":
            combined = "STRONGLY_RESTRICTIVE"
        elif fed_bias == "BEARISH" or swf_trend == "RISK_OFF":
            combined = "RESTRICTIVE"
        else:
            combined = "NEUTRAL"

        return {
            "timestamp": datetime.now().isoformat(),
            "fed": fed_data,
            "swf": swf_data,
            "combined_liquidity_conditions": combined,
            "strategic_implications": self._get_implications(combined)
        }

    def _get_implications(self, conditions: str) -> List[str]:
        """Get strategic implications of liquidity conditions"""
        implications = {
            "STRONGLY_SUPPORTIVE": [
                "Risk assets have tailwind from liquidity",
                "Consider overweight equities",
                "Momentum strategies favored",
                "Volatility likely compressed"
            ],
            "SUPPORTIVE": [
                "Mild tailwind for risk assets",
                "Standard positioning appropriate",
                "Watch for changes in Fed stance"
            ],
            "NEUTRAL": [
                "No clear liquidity bias",
                "Focus on individual opportunities",
                "Balanced risk approach"
            ],
            "RESTRICTIVE": [
                "Mild headwind for risk assets",
                "Consider defensive tilts",
                "Quality over speculation"
            ],
            "STRONGLY_RESTRICTIVE": [
                "Significant headwind from liquidity drain",
                "Reduce risk exposure",
                "Favor cash and short duration",
                "Volatility likely elevated"
            ]
        }

        return implications.get(conditions, ["Unable to determine implications"])


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SOVEREIGN & MACRO LIQUIDITY MONITOR")
    print("=" * 60)

    monitor = SovereignMonitor()

    # Get liquidity conditions
    conditions = monitor.get_liquidity_conditions()

    print("\n=== FED BALANCE SHEET ===")
    fed = conditions["fed"]
    print(f"  Total Assets: ${fed['current_balance_sheet_billions']:.0f}B")
    print(f"  Net Liquidity: ${fed['net_liquidity_billions']:.0f}B")
    print(f"  Monthly Change: ${fed['monthly_total_change_billions']:.0f}B")
    print(f"  Interpretation: {fed['interpretation']}")
    print(f"  Risk Asset Bias: {fed['risk_asset_bias']}")

    print("\n=== SWF FLOWS ===")
    swf = conditions["swf"]
    print(f"  Total AUM: ${swf['total_aum_billions']:.0f}B")
    print(f"  Monthly Flow: ${swf['monthly_net_flow_billions']:.1f}B")
    print(f"  Avg Equity Allocation: {swf['avg_equity_allocation_pct']:.1f}%")
    print(f"  Trend: {swf['aggregate_trend']}")

    print("\n=== COMBINED ASSESSMENT ===")
    print(f"  Liquidity Conditions: {conditions['combined_liquidity_conditions']}")
    print(f"  Strategic Implications:")
    for impl in conditions['strategic_implications']:
        print(f"    - {impl}")
