"""
Arbitrage Calculator

Calculates spread opportunities between Polymarket and Kalshi markets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity between two markets."""
    
    # Market identifiers
    kalshi_id: str
    polymarket_id: str
    
    # Market titles
    kalshi_title: str
    polymarket_title: str
    
    # Current prices (0-1 scale)
    kalshi_yes: float
    kalshi_no: float
    polymarket_yes: float
    polymarket_no: float
    
    # Calculated spread
    spread: float  # Positive = opportunity
    spread_pct: float  # As percentage
    
    # Direction of arbitrage
    direction: str  # "buy_poly_sell_kalshi" or "buy_kalshi_sell_poly"
    
    # Match quality
    similarity: float
    match_type: str
    
    # URLs
    kalshi_url: str
    polymarket_url: str
    
    # Timestamps
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Historical tracking
    spread_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def is_profitable(self) -> bool:
        """Check if this opportunity is profitable after fees."""
        # Assume ~2% total fees (1% per platform)
        return self.spread_pct > 2.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'kalshi_id': self.kalshi_id,
            'polymarket_id': self.polymarket_id,
            'kalshi_title': self.kalshi_title,
            'polymarket_title': self.polymarket_title,
            'kalshi_yes': self.kalshi_yes,
            'kalshi_no': self.kalshi_no,
            'polymarket_yes': self.polymarket_yes,
            'polymarket_no': self.polymarket_no,
            'spread': self.spread,
            'spread_pct': self.spread_pct,
            'direction': self.direction,
            'similarity': self.similarity,
            'match_type': self.match_type,
            'kalshi_url': self.kalshi_url,
            'polymarket_url': self.polymarket_url,
            'detected_at': self.detected_at.isoformat(),
            'is_profitable': self.is_profitable(),
        }


class ArbitrageCalculator:
    """Calculates arbitrage opportunities between matched markets."""
    
    def __init__(self, min_spread_pct: float = 1.0):
        self.min_spread_pct = min_spread_pct
        self.opportunities: List[ArbitrageOpportunity] = []
        self.history: List[Dict[str, Any]] = []
    
    def calculate_spread(
        self,
        kalshi_market: Dict[str, Any],
        polymarket_market: Dict[str, Any],
        similarity: float,
        match_type: str,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Calculate spread between two matched markets.
        
        Arbitrage exists when:
        - Poly YES + Kalshi NO < 1 (profit from YES happening)
        - Poly NO + Kalshi YES < 1 (profit from NO happening)
        
        Args:
            kalshi_market: Simplified Kalshi market
            polymarket_market: Simplified Polymarket market
            similarity: Match similarity score
            match_type: Type of match (manual, fuzzy)
            
        Returns:
            ArbitrageOpportunity if spread exists, None otherwise
        """
        k_yes = kalshi_market.get('yes_price', 0)
        k_no = kalshi_market.get('no_price', 0) or (1 - k_yes)
        p_yes = polymarket_market.get('yes_price', 0)
        p_no = polymarket_market.get('no_price', 0) or (1 - p_yes)
        
        # Skip if prices are 0 or invalid
        if k_yes <= 0 or p_yes <= 0:
            return None
        
        # Calculate both directions
        # Direction 1: Buy Poly YES + Kalshi NO
        # Cost = p_yes + k_no, Payout = 1 if YES, 1 if NO = 1 always
        # Spread = 1 - (p_yes + k_no)
        spread1 = 1.0 - (p_yes + k_no)
        
        # Direction 2: Buy Poly NO + Kalshi YES  
        # Spread = 1 - (p_no + k_yes)
        spread2 = 1.0 - (p_no + k_yes)
        
        # Use the better spread
        if spread1 >= spread2:
            spread = spread1
            direction = "buy_poly_yes_kalshi_no"
        else:
            spread = spread2
            direction = "buy_poly_no_kalshi_yes"
        
        spread_pct = spread * 100
        
        # Skip if spread is below threshold
        if spread_pct < self.min_spread_pct:
            return None
        
        opportunity = ArbitrageOpportunity(
            kalshi_id=kalshi_market.get('id', ''),
            polymarket_id=polymarket_market.get('id', ''),
            kalshi_title=kalshi_market.get('title', ''),
            polymarket_title=polymarket_market.get('title', ''),
            kalshi_yes=k_yes,
            kalshi_no=k_no,
            polymarket_yes=p_yes,
            polymarket_no=p_no,
            spread=spread,
            spread_pct=spread_pct,
            direction=direction,
            similarity=similarity,
            match_type=match_type,
            kalshi_url=kalshi_market.get('url', ''),
            polymarket_url=polymarket_market.get('url', ''),
        )
        
        return opportunity
    
    def find_opportunities(
        self,
        matched_markets: List[Dict[str, Any]],
    ) -> List[ArbitrageOpportunity]:
        """
        Find all arbitrage opportunities from matched markets.
        
        Args:
            matched_markets: List of matched market pairs from MarketMatcher
            
        Returns:
            List of ArbitrageOpportunity objects, sorted by spread descending
        """
        opportunities = []
        
        for match in matched_markets:
            kalshi = match.get('kalshi', {})
            polymarket = match.get('polymarket', {})
            similarity = match.get('similarity', 0)
            match_type = match.get('match_type', 'unknown')
            
            opp = self.calculate_spread(kalshi, polymarket, similarity, match_type)
            if opp:
                opportunities.append(opp)
        
        # Sort by spread percentage descending
        opportunities.sort(key=lambda x: x.spread_pct, reverse=True)
        
        self.opportunities = opportunities
        
        # Record history
        self.history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'count': len(opportunities),
            'top_spread': opportunities[0].spread_pct if opportunities else 0,
        })
        
        return opportunities
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of current opportunities."""
        if not self.opportunities:
            return {
                'count': 0,
                'profitable_count': 0,
                'avg_spread': 0,
                'max_spread': 0,
                'top_opportunities': [],
            }
        
        profitable = [o for o in self.opportunities if o.is_profitable()]
        spreads = [o.spread_pct for o in self.opportunities]
        
        return {
            'count': len(self.opportunities),
            'profitable_count': len(profitable),
            'avg_spread': sum(spreads) / len(spreads),
            'max_spread': max(spreads),
            'top_opportunities': [o.to_dict() for o in self.opportunities[:10]],
        }


if __name__ == "__main__":
    # Test calculation
    kalshi = {
        'id': 'SPACEX-IPO-2025',
        'title': 'SpaceX IPO in 2025',
        'yes_price': 0.20,
        'no_price': 0.80,
        'url': 'https://kalshi.com/markets/spacex',
    }
    
    poly = {
        'id': 'spacex-ipo',
        'title': 'Will SpaceX IPO before 2026?',
        'yes_price': 0.82,
        'no_price': 0.18,
        'url': 'https://polymarket.com/event/spacex-ipo',
    }
    
    calc = ArbitrageCalculator(min_spread_pct=1.0)
    opp = calc.calculate_spread(kalshi, poly, 85.0, 'fuzzy')
    
    if opp:
        print(f"Opportunity found!")
        print(f"  Spread: {opp.spread_pct:.2f}%")
        print(f"  Direction: {opp.direction}")
        print(f"  Profitable: {opp.is_profitable()}")
    else:
        print("No opportunity found")
