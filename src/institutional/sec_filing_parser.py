"""
SEC FILING PARSER
13F Analysis and Institutional Ownership Tracking
Built for: Travis @ Trav's Trader Lounge

This module tracks:
1. 13F Filings - Quarterly institutional holdings
2. Conviction Patterns - Multi-quarter accumulation
3. Ownership Concentration - Crowding risk

13F data is lagged (45 days after quarter end) but valuable for:
- Position-level trades (weeks to months)
- Detecting institutional conviction
- Identifying crowded trades
"""

import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Holding:
    """Single holding in a 13F filing"""
    cusip: str
    issuer: str
    symbol: Optional[str]
    shares: int
    value: float              # In thousands
    share_change: int = 0     # vs previous quarter
    pct_change: float = 0.0
    investment_discretion: str = "SOLE"
    voting_authority: str = "SOLE"


@dataclass
class Filing13F:
    """Parsed 13F filing"""
    cik: str
    filer_name: str
    filing_date: date
    report_date: date         # End of quarter
    total_value: float        # Total AUM in millions
    holdings: List[Holding] = field(default_factory=list)
    filing_url: str = ""

    @property
    def holdings_count(self) -> int:
        return len(self.holdings)

    @property
    def top_holdings(self) -> List[Holding]:
        return sorted(self.holdings, key=lambda h: -h.value)[:10]


@dataclass
class HoldingChange:
    """Change in holding between quarters"""
    symbol: str
    issuer: str
    previous_shares: int
    current_shares: int
    share_change: int
    pct_change: float
    previous_value: float
    current_value: float
    action: str              # NEW, INCREASED, DECREASED, SOLD, UNCHANGED


@dataclass
class ConvictionPattern:
    """Multi-quarter conviction pattern"""
    symbol: str
    filer_name: str
    cik: str
    quarters_held: int
    quarters_increased: int
    total_share_change: int
    total_pct_change: float
    current_shares: int
    current_value: float
    conviction_score: float   # 0-100


class SECEdgarClient:
    """
    Client for SEC EDGAR API.

    Rate limit: 10 requests per second
    User-Agent required
    """

    BASE_URL = "https://www.sec.gov"
    DATA_URL = "https://data.sec.gov"

    def __init__(self, user_agent: str = "TradingPlatform/1.0 (contact@example.com)"):
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json"
        })
        self._last_request = 0
        self._rate_limit = 0.1  # 10 requests/sec

        logger.info("SEC EDGAR Client initialized")

    def _rate_limit_wait(self):
        """Respect SEC rate limits"""
        elapsed = time.time() - self._last_request
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request = time.time()

    def get_company_cik(self, ticker: str) -> Optional[str]:
        """Look up CIK for a ticker symbol"""
        self._rate_limit_wait()

        url = f"{self.DATA_URL}/submissions/CIK{ticker.upper()}.json"

        try:
            # Try ticker lookup first
            response = self.session.get(
                f"{self.BASE_URL}/cgi-bin/browse-edgar",
                params={
                    "action": "getcompany",
                    "CIK": ticker,
                    "type": "13F",
                    "output": "atom"
                }
            )

            if response.ok:
                # Parse CIK from response
                # This is simplified - real parsing would extract from XML
                return None  # Would return actual CIK
        except Exception as e:
            logger.error(f"CIK lookup failed for {ticker}: {e}")

        return None

    def get_13f_filings(
        self,
        cik: str,
        limit: int = 4
    ) -> List[Dict]:
        """Get recent 13F filings for a CIK"""
        self._rate_limit_wait()

        # Normalize CIK to 10 digits
        cik = cik.zfill(10)

        url = f"{self.DATA_URL}/submissions/CIK{cik}.json"

        try:
            response = self.session.get(url)
            response.raise_for_status()

            data = response.json()
            filings = data.get("filings", {}).get("recent", {})

            # Filter to 13F-HR filings
            results = []
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accessions = filings.get("accessionNumber", [])

            for i, form in enumerate(forms):
                if "13F" in form and len(results) < limit:
                    results.append({
                        "form": form,
                        "filing_date": dates[i],
                        "accession": accessions[i].replace("-", ""),
                        "cik": cik
                    })

            return results

        except Exception as e:
            logger.error(f"Failed to get 13F filings for CIK {cik}: {e}")
            return []

    def parse_13f_holdings(
        self,
        cik: str,
        accession: str
    ) -> List[Holding]:
        """Parse holdings from a 13F filing"""
        self._rate_limit_wait()

        # In production, would fetch and parse the XML
        # For now, return mock data
        logger.info(f"Would parse 13F for CIK {cik}, accession {accession}")
        return []


class InstitutionalTracker:
    """
    Track institutional ownership and detect patterns.

    Key signals:
    1. Conviction building - Multi-quarter accumulation
    2. Crowded trades - High institutional concentration
    3. Smart money divergence - Top funds vs rest
    """

    # Major institutional filers to track
    TOP_FUNDS = {
        "0001067983": "Berkshire Hathaway",
        "0001336528": "Renaissance Technologies",
        "0001350694": "Citadel",
        "0001364742": "Bridgewater",
        "0001061768": "D.E. Shaw",
        "0001037389": "Baupost",
        "0001103804": "Elliott Management",
        "0001273087": "Pershing Square",
        "0001510883": "Soros Fund Management",
        "0001649339": "Third Point",
    }

    def __init__(self, edgar_client: Optional[SECEdgarClient] = None):
        self.edgar = edgar_client or SECEdgarClient()
        self._holdings_cache: Dict[str, Dict[str, Filing13F]] = {}  # {cik: {quarter: filing}}
        self._symbol_to_cusip: Dict[str, str] = {}

        logger.info("Institutional Tracker initialized")

    def get_fund_holdings(
        self,
        cik: str,
        quarters: int = 4
    ) -> List[Filing13F]:
        """Get historical 13F filings for a fund"""
        # Check cache
        if cik in self._holdings_cache:
            cached = list(self._holdings_cache[cik].values())
            if len(cached) >= quarters:
                return sorted(cached, key=lambda f: f.report_date, reverse=True)[:quarters]

        # Fetch from SEC
        filings_meta = self.edgar.get_13f_filings(cik, limit=quarters)

        filings = []
        for meta in filings_meta:
            # In production, would parse actual filing
            # For now, create mock filing
            filing = self._mock_filing(cik, meta)
            filings.append(filing)

            # Cache
            quarter_key = filing.report_date.strftime("%Y-Q%q")
            if cik not in self._holdings_cache:
                self._holdings_cache[cik] = {}
            self._holdings_cache[cik][quarter_key] = filing

        return filings

    def _mock_filing(self, cik: str, meta: Dict) -> Filing13F:
        """Create mock filing for testing"""
        import random

        filing_date = datetime.strptime(meta.get("filing_date", "2024-01-15"), "%Y-%m-%d").date()

        # Generate mock holdings
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM", "V"]
        holdings = []

        for sym in symbols:
            shares = random.randint(100000, 10000000)
            price = random.uniform(100, 500)
            holdings.append(Holding(
                cusip=f"CUSIP_{sym}",
                issuer=f"{sym} Inc",
                symbol=sym,
                shares=shares,
                value=shares * price / 1000,  # In thousands
                share_change=random.randint(-500000, 500000),
                pct_change=random.uniform(-20, 30)
            ))

        return Filing13F(
            cik=cik,
            filer_name=self.TOP_FUNDS.get(cik, f"Fund {cik}"),
            filing_date=filing_date,
            report_date=filing_date - timedelta(days=45),  # Approximate quarter end
            total_value=sum(h.value for h in holdings) / 1000,  # In millions
            holdings=holdings,
            filing_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
        )

    def detect_conviction_patterns(
        self,
        symbol: str,
        min_quarters: int = 3,
        min_funds: int = 3
    ) -> Dict:
        """
        Detect multi-quarter conviction building.

        Looks for funds that have increased position for N consecutive quarters.
        """
        conviction_patterns = []

        for cik, fund_name in self.TOP_FUNDS.items():
            filings = self.get_fund_holdings(cik, quarters=4)

            if len(filings) < min_quarters:
                continue

            # Track symbol across quarters
            quarters_increased = 0
            quarters_held = 0
            prev_shares = 0
            current_shares = 0
            current_value = 0

            for filing in reversed(filings):  # Oldest to newest
                for holding in filing.holdings:
                    if holding.symbol == symbol:
                        quarters_held += 1
                        current_shares = holding.shares
                        current_value = holding.value

                        if prev_shares > 0 and holding.shares > prev_shares:
                            quarters_increased += 1

                        prev_shares = holding.shares
                        break

            if quarters_held >= min_quarters and quarters_increased >= 2:
                # Calculate conviction score
                conviction_score = min(100, (quarters_increased / quarters_held) * 100 + 20)

                conviction_patterns.append(ConvictionPattern(
                    symbol=symbol,
                    filer_name=fund_name,
                    cik=cik,
                    quarters_held=quarters_held,
                    quarters_increased=quarters_increased,
                    total_share_change=current_shares - prev_shares,
                    total_pct_change=((current_shares - prev_shares) / prev_shares * 100) if prev_shares else 0,
                    current_shares=current_shares,
                    current_value=current_value,
                    conviction_score=conviction_score
                ))

        # Filter to funds showing conviction
        showing_conviction = [p for p in conviction_patterns if p.conviction_score >= 60]

        return {
            "symbol": symbol,
            "patterns_found": len(conviction_patterns),
            "funds_showing_conviction": len(showing_conviction),
            "meets_threshold": len(showing_conviction) >= min_funds,
            "patterns": [
                {
                    "fund": p.filer_name,
                    "quarters_held": p.quarters_held,
                    "quarters_increased": p.quarters_increased,
                    "conviction_score": p.conviction_score,
                    "current_value_millions": p.current_value / 1000
                }
                for p in sorted(showing_conviction, key=lambda x: -x.conviction_score)
            ],
            "aggregate_conviction_score": (
                sum(p.conviction_score for p in showing_conviction) / len(showing_conviction)
                if showing_conviction else 0
            )
        }

    def calculate_ownership_concentration(self, symbol: str) -> Dict:
        """
        Calculate institutional ownership concentration.

        High concentration = crowded trade = liquidation risk
        """
        total_institutional_shares = 0
        top_10_shares = 0
        fund_holdings = []

        for cik, fund_name in self.TOP_FUNDS.items():
            filings = self.get_fund_holdings(cik, quarters=1)

            if not filings:
                continue

            for holding in filings[0].holdings:
                if holding.symbol == symbol:
                    fund_holdings.append({
                        "fund": fund_name,
                        "shares": holding.shares,
                        "value": holding.value
                    })
                    total_institutional_shares += holding.shares
                    break

        # Sort by holdings
        fund_holdings.sort(key=lambda x: -x["shares"])

        # Top 10 concentration
        top_10 = fund_holdings[:10]
        top_10_shares = sum(h["shares"] for h in top_10)

        concentration_pct = (top_10_shares / total_institutional_shares * 100) if total_institutional_shares else 0

        # Crowded trade risk
        if concentration_pct > 60:
            risk = "HIGH"
        elif concentration_pct > 40:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        return {
            "symbol": symbol,
            "total_institutional_shares": total_institutional_shares,
            "top_10_concentration_pct": concentration_pct,
            "crowded_trade_risk": risk,
            "top_holders": [
                {"fund": h["fund"], "shares": h["shares"], "value_millions": h["value"] / 1000}
                for h in top_10[:5]
            ],
            "interpretation": (
                f"{risk} concentration risk. " +
                ("Top 10 funds own majority - liquidation risk if sentiment shifts." if risk == "HIGH"
                 else "Moderate concentration - monitor for changes." if risk == "MEDIUM"
                 else "Diversified ownership - lower crowding risk.")
            )
        }

    def get_smart_money_moves(self, quarters: int = 2) -> List[Dict]:
        """
        Get recent notable moves by top funds.

        Identifies:
        - New positions
        - Complete exits
        - Large increases/decreases
        """
        moves = []

        for cik, fund_name in self.TOP_FUNDS.items():
            filings = self.get_fund_holdings(cik, quarters=2)

            if len(filings) < 2:
                continue

            current = filings[0]
            previous = filings[1]

            # Create lookup
            prev_holdings = {h.symbol: h for h in previous.holdings if h.symbol}
            curr_holdings = {h.symbol: h for h in current.holdings if h.symbol}

            # Find changes
            for symbol, holding in curr_holdings.items():
                prev = prev_holdings.get(symbol)

                if prev is None:
                    # New position
                    if holding.value > 50000:  # > $50M
                        moves.append({
                            "fund": fund_name,
                            "symbol": symbol,
                            "action": "NEW_POSITION",
                            "shares": holding.shares,
                            "value_millions": holding.value / 1000,
                            "significance": "HIGH"
                        })
                elif holding.shares > prev.shares * 1.5:
                    # Increased 50%+
                    moves.append({
                        "fund": fund_name,
                        "symbol": symbol,
                        "action": "INCREASED",
                        "change_pct": (holding.shares / prev.shares - 1) * 100,
                        "value_millions": holding.value / 1000,
                        "significance": "MEDIUM"
                    })

            # Find exits
            for symbol, prev_holding in prev_holdings.items():
                if symbol not in curr_holdings:
                    if prev_holding.value > 50000:  # Was > $50M
                        moves.append({
                            "fund": fund_name,
                            "symbol": symbol,
                            "action": "EXITED",
                            "previous_value_millions": prev_holding.value / 1000,
                            "significance": "HIGH"
                        })

        return sorted(moves, key=lambda m: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[m.get("significance", "LOW")])


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("INSTITUTIONAL TRACKING")
    print("=" * 60)

    # Initialize
    edgar = SECEdgarClient("TradingPlatform/1.0 (test@example.com)")
    tracker = InstitutionalTracker(edgar)

    # Detect conviction patterns
    print("\n=== CONVICTION PATTERNS: NVDA ===")
    conviction = tracker.detect_conviction_patterns("NVDA")
    print(f"Funds analyzed: {conviction['patterns_found']}")
    print(f"Funds showing conviction: {conviction['funds_showing_conviction']}")
    print(f"Meets threshold: {conviction['meets_threshold']}")

    for p in conviction['patterns'][:3]:
        print(f"  {p['fund']}: {p['quarters_increased']}/{p['quarters_held']} quarters up, score: {p['conviction_score']:.1f}")

    # Ownership concentration
    print("\n=== OWNERSHIP CONCENTRATION: AAPL ===")
    concentration = tracker.calculate_ownership_concentration("AAPL")
    print(f"Top 10 concentration: {concentration['top_10_concentration_pct']:.1f}%")
    print(f"Crowded trade risk: {concentration['crowded_trade_risk']}")
    print(f"Interpretation: {concentration['interpretation']}")

    # Smart money moves
    print("\n=== RECENT SMART MONEY MOVES ===")
    moves = tracker.get_smart_money_moves()
    for move in moves[:5]:
        print(f"  {move['fund']}: {move['action']} {move['symbol']}")
