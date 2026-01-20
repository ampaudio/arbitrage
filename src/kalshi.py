"""
Kalshi API Client

Fetches market data from Kalshi using:
- Base URL: https://api.elections.kalshi.com/trade-api/v2
"""
from __future__ import annotations

import requests
from typing import Any, Dict, List, Optional
from datetime import datetime
import warnings

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiClient:
    """Client for Kalshi API endpoints."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ArbitrageMonitor/1.0",
            "Accept": "application/json",
        })
    
    def get_markets(
        self, 
        status: str = "open",
        limit: int = 200,
        cursor: Optional[str] = None,
        series_ticker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch markets from Kalshi API.
        
        Args:
            status: Market status filter (open, closed, etc.)
            limit: Maximum number of markets to return
            cursor: Pagination cursor
            series_ticker: Filter by series
            
        Returns:
            Response dictionary with 'markets' list and 'cursor'
        """
        url = f"{KALSHI_BASE_URL}/markets"
        params = {
            "status": status,
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Kalshi markets: {e}")
            return {"markets": [], "cursor": None}
    
    def get_all_markets(self, status: str = "open", max_pages: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch all markets with pagination.
        
        Args:
            status: Market status filter
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of all market dictionaries
        """
        all_markets = []
        cursor = None
        
        for _ in range(max_pages):
            result = self.get_markets(status=status, limit=200, cursor=cursor)
            markets = result.get("markets", [])
            all_markets.extend(markets)
            
            cursor = result.get("cursor")
            if not cursor or not markets:
                break
        
        return all_markets
    
    def get_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific market by ticker.
        
        Args:
            ticker: Market ticker
            
        Returns:
            Market dictionary or None
        """
        url = f"{KALSHI_BASE_URL}/markets/{ticker}"
        
        try:
            response = self.session.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json().get("market")
        except requests.RequestException as e:
            print(f"Error fetching Kalshi market {ticker}: {e}")
            return None
    
    def get_event(self, event_ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch event details.
        
        Args:
            event_ticker: Event ticker
            
        Returns:
            Event dictionary or None
        """
        url = f"{KALSHI_BASE_URL}/events/{event_ticker}"
        
        try:
            response = self.session.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json().get("event")
        except requests.RequestException as e:
            print(f"Error fetching Kalshi event {event_ticker}: {e}")
            return None
    
    def get_series(self, series_ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch series details.
        
        Args:
            series_ticker: Series ticker
            
        Returns:
            Series dictionary or None
        """
        url = f"{KALSHI_BASE_URL}/series/{series_ticker}"
        
        try:
            response = self.session.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json().get("series")
        except requests.RequestException as e:
            print(f"Error fetching Kalshi series {series_ticker}: {e}")
            return None
    
    def get_orderbook(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch orderbook for a market.
        
        Args:
            ticker: Market ticker
            
        Returns:
            Orderbook dictionary or None
        """
        url = f"{KALSHI_BASE_URL}/markets/{ticker}/orderbook"
        
        try:
            response = self.session.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json().get("orderbook")
        except requests.RequestException as e:
            print(f"Error fetching Kalshi orderbook {ticker}: {e}")
            return None
    
    def get_simplified_markets(self) -> List[Dict[str, Any]]:
        """
        Get markets in simplified format for matching.
        
        Returns:
            List of simplified market dictionaries with:
            - id: Market ticker
            - title: Market title
            - yes_price: Current YES price (0-1)
            - no_price: Current NO price (0-1)
            - volume: Trading volume
            - end_date: Market close time
            - url: Link to market
        """
        markets = self.get_all_markets(status="open")
        simplified = []
        
        for market in markets:
            try:
                # Kalshi prices are in cents (0-100), convert to 0-1
                # Priority: yes_bid > last_price > 0
                yes_bid = float(market.get("yes_bid", 0) or 0)
                yes_ask = float(market.get("yes_ask", 0) or 0)
                last_price = float(market.get("last_price", 0) or 0)
                
                # Use mid-point of bid/ask if available, otherwise last_price
                if yes_bid > 0 and yes_ask > 0:
                    yes_price = (yes_bid + yes_ask) / 2 / 100.0
                elif yes_bid > 0:
                    yes_price = yes_bid / 100.0
                elif last_price > 0:
                    yes_price = last_price / 100.0
                else:
                    # Skip markets with no price data
                    continue
                
                no_price = 1.0 - yes_price
                
                ticker = market.get("ticker", "")
                series = market.get("series_ticker", "")
                title = market.get("title", "")
                
                # Include all markets with valid prices (no filtering by title)
                
                simplified.append({
                    "id": ticker,
                    "title": title,
                    "subtitle": market.get("subtitle", ""),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": float(market.get("volume", 0) or 0),
                    "end_date": market.get("close_time", ""),
                    "url": f"https://kalshi.com/markets/{series.lower()}/{ticker.lower()}" if series else f"https://kalshi.com/markets/{ticker.lower()}",
                    "platform": "kalshi",
                    "event_ticker": market.get("event_ticker", ""),
                    "series_ticker": series,
                    "category": market.get("category", ""),
                })
            except (ValueError, TypeError, KeyError) as e:
                continue
        
        return simplified


if __name__ == "__main__":
    # Quick test
    client = KalshiClient()
    markets = client.get_simplified_markets()
    print(f"Loaded {len(markets)} Kalshi markets")
    for m in markets[:5]:
        print(f"  - {m['title'][:60]}... YES: {m['yes_price']:.2f}")
