"""
Polymarket API Client

Fetches market data from Polymarket using:
- Gamma API: https://gamma-api.polymarket.com - Market discovery & metadata
- CLOB API: https://clob.polymarket.com - Real-time prices & orderbook
"""
from __future__ import annotations

import requests
from typing import Any, Dict, List, Optional
from datetime import datetime
import warnings

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"


class PolymarketClient:
    """Client for Polymarket API endpoints."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ArbitrageMonitor/1.0",
            "Accept": "application/json",
        })
    
    def get_events(self, limit: int = 100, active: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch events from Gamma API.
        
        Args:
            limit: Maximum number of events to return
            active: Only return active events
            
        Returns:
            List of event dictionaries
        """
        url = f"{GAMMA_BASE_URL}/events"
        params = {
            "limit": limit,
            "active": "true" if active else "false",
        }
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Polymarket events: {e}")
            return []
    
    def get_markets(self, limit: int = 100, active: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch markets from Gamma API.
        
        Args:
            limit: Maximum number of markets to return
            active: Only return active markets
            
        Returns:
            List of market dictionaries with prices
        """
        url = f"{GAMMA_BASE_URL}/markets"
        params = {
            "limit": limit,
            "active": "true" if active else "false",
            "closed": "false",  # Only get non-closed markets
        }
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Polymarket markets: {e}")
            return []
    
    def get_market_by_id(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific market by condition ID.
        
        Args:
            condition_id: The market condition ID
            
        Returns:
            Market dictionary or None
        """
        url = f"{GAMMA_BASE_URL}/markets/{condition_id}"
        
        try:
            response = self.session.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Polymarket market {condition_id}: {e}")
            return None
    
    def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch orderbook from CLOB API.
        
        Args:
            token_id: The outcome token ID
            
        Returns:
            Orderbook dictionary or None
        """
        url = f"{CLOB_BASE_URL}/book"
        params = {"token_id": token_id}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Polymarket orderbook: {e}")
            return None
    
    def get_price(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current price from CLOB API.
        
        Args:
            token_id: The outcome token ID
            
        Returns:
            Price dictionary or None
        """
        url = f"{CLOB_BASE_URL}/price"
        params = {"token_id": token_id}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Polymarket price: {e}")
            return None
    
    def get_simplified_markets(self) -> List[Dict[str, Any]]:
        """
        Get markets in simplified format for matching.
        
        Returns:
            List of simplified market dictionaries with:
            - id: Market ID
            - title: Market question/title
            - yes_price: Current YES price (0-1)
            - no_price: Current NO price (0-1)
            - volume: Trading volume
            - end_date: Market end date
            - url: Link to market
        """
        markets = self.get_markets(limit=500, active=True)
        simplified = []
        
        for market in markets:
            try:
                # Extract price from outcomePrices if available
                yes_price = 0.0
                no_price = 0.0
                
                if "outcomePrices" in market and market["outcomePrices"]:
                    prices = market["outcomePrices"]
                    if isinstance(prices, str):
                        # Parse "[\"0.85\", \"0.15\"]" format - remove brackets and quotes
                        import json
                        try:
                            prices = json.loads(prices)
                            if len(prices) >= 2:
                                yes_price = float(prices[0])
                                no_price = float(prices[1])
                        except json.JSONDecodeError:
                            # Fallback: manual parsing
                            prices = prices.strip("[]").replace('"', '').split(",")
                            if len(prices) >= 2:
                                yes_price = float(prices[0].strip())
                                no_price = float(prices[1].strip())
                    elif isinstance(prices, list) and len(prices) >= 2:
                        yes_price = float(prices[0])
                        no_price = float(prices[1])
                
                simplified.append({
                    "id": market.get("id") or market.get("conditionId", ""),
                    "title": market.get("question") or market.get("title", ""),
                    "description": market.get("description", ""),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": float(market.get("volume", 0) or 0),
                    "end_date": market.get("endDate") or market.get("end_date_iso", ""),
                    "url": f"https://polymarket.com/event/{market.get('slug', market.get('id', ''))}",
                    "platform": "polymarket",
                })
            except (ValueError, TypeError, KeyError) as e:
                continue
        
        return simplified


if __name__ == "__main__":
    # Quick test
    client = PolymarketClient()
    markets = client.get_simplified_markets()
    print(f"Loaded {len(markets)} Polymarket markets")
    for m in markets[:5]:
        print(f"  - {m['title'][:60]}... YES: {m['yes_price']:.2f}")
