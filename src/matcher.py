"""
Market Matcher

Matches similar markets between Polymarket and Kalshi using fuzzy text matching.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from fuzzywuzzy import fuzz
from fuzzywuzzy import process


def normalize_text(text: str) -> str:
    """
    Normalize text for matching.
    
    - Lowercase
    - Remove punctuation
    - Remove common words
    - Normalize whitespace
    """
    if not text:
        return ""
    
    text = text.lower()
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove punctuation except hyphens
    text = re.sub(r'[^\w\s-]', ' ', text)
    # Remove common words that don't add meaning
    stop_words = {'the', 'a', 'an', 'will', 'be', 'is', 'are', 'by', 'on', 'in', 'at', 'to', 'for', 'of'}
    words = text.split()
    words = [w for w in words if w not in stop_words and len(w) > 1]
    # Normalize whitespace
    return ' '.join(words)


def extract_keywords(text: str) -> set:
    """Extract important keywords from text."""
    normalized = normalize_text(text)
    
    # Extract potential names, dates, numbers
    keywords = set()
    words = normalized.split()
    
    for word in words:
        # Keep if it's a number or longer than 2 chars
        if word.isdigit() or len(word) > 2:
            keywords.add(word)
    
    return keywords


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two texts.
    
    Returns a score from 0 to 100.
    """
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Token set ratio handles word order differences well
    token_score = fuzz.token_set_ratio(norm1, norm2)
    
    # Partial ratio for substring matching
    partial_score = fuzz.partial_ratio(norm1, norm2)
    
    # Keyword overlap bonus
    keywords1 = extract_keywords(text1)
    keywords2 = extract_keywords(text2)
    if keywords1 and keywords2:
        overlap = len(keywords1 & keywords2) / max(len(keywords1), len(keywords2))
        keyword_score = overlap * 100
    else:
        keyword_score = 0
    
    # Weighted average
    final_score = (token_score * 0.4) + (partial_score * 0.35) + (keyword_score * 0.25)
    
    return final_score


class MarketMatcher:
    """Matches markets between platforms using fuzzy matching."""
    
    def __init__(self, similarity_threshold: float = 70.0):
        self.similarity_threshold = similarity_threshold
        self.manual_mappings: Dict[str, str] = {}  # Kalshi ID -> Polymarket ID
    
    def add_manual_mapping(self, kalshi_id: str, polymarket_id: str):
        """Add a manual market mapping."""
        self.manual_mappings[kalshi_id] = polymarket_id
    
    def find_matches(
        self,
        kalshi_markets: List[Dict[str, Any]],
        polymarket_markets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Find matching markets between platforms.
        
        Args:
            kalshi_markets: List of simplified Kalshi markets
            polymarket_markets: List of simplified Polymarket markets
            
        Returns:
            List of matched market pairs with similarity scores
        """
        matches = []
        poly_titles = [(m['title'], m) for m in polymarket_markets]
        
        for kalshi_market in kalshi_markets:
            kalshi_title = kalshi_market.get('title', '')
            kalshi_subtitle = kalshi_market.get('subtitle', '')
            kalshi_full = f"{kalshi_title} {kalshi_subtitle}".strip()
            
            # Check manual mappings first
            if kalshi_market['id'] in self.manual_mappings:
                poly_id = self.manual_mappings[kalshi_market['id']]
                poly_match = next((m for m in polymarket_markets if m['id'] == poly_id), None)
                if poly_match:
                    matches.append({
                        'kalshi': kalshi_market,
                        'polymarket': poly_match,
                        'similarity': 100.0,
                        'match_type': 'manual',
                    })
                    continue
            
            # Fuzzy match
            best_score = 0.0
            best_match = None
            
            for poly_title, poly_market in poly_titles:
                poly_desc = poly_market.get('description', '')
                poly_full = f"{poly_title} {poly_desc}".strip()
                
                # Try matching with just titles
                score1 = calculate_similarity(kalshi_title, poly_title)
                
                # Try matching with full text
                score2 = calculate_similarity(kalshi_full, poly_full)
                
                # Use best score
                score = max(score1, score2)
                
                if score > best_score:
                    best_score = score
                    best_match = poly_market
            
            if best_match and best_score >= self.similarity_threshold:
                matches.append({
                    'kalshi': kalshi_market,
                    'polymarket': best_match,
                    'similarity': best_score,
                    'match_type': 'fuzzy',
                })
        
        # Sort by similarity descending
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        return matches
    
    def find_best_match(
        self,
        market: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Find the best matching market from candidates.
        
        Args:
            market: The market to match
            candidates: List of candidate markets
            
        Returns:
            Tuple of (best_match, similarity) or None
        """
        market_title = market.get('title', '')
        market_desc = market.get('description', '') or market.get('subtitle', '')
        market_full = f"{market_title} {market_desc}".strip()
        
        best_score = 0.0
        best_match = None
        
        for candidate in candidates:
            cand_title = candidate.get('title', '')
            cand_desc = candidate.get('description', '') or candidate.get('subtitle', '')
            cand_full = f"{cand_title} {cand_desc}".strip()
            
            score = max(
                calculate_similarity(market_title, cand_title),
                calculate_similarity(market_full, cand_full),
            )
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_match and best_score >= self.similarity_threshold:
            return (best_match, best_score)
        
        return None


if __name__ == "__main__":
    # Test similarity
    test_cases = [
        ("Will SpaceX IPO in 2025?", "SpaceX IPO by end of 2025"),
        ("Trump wins 2024 election", "Donald Trump to win 2024 presidential election"),
        ("Bitcoin above $100k", "Will Bitcoin reach $100,000?"),
    ]
    
    for t1, t2 in test_cases:
        score = calculate_similarity(t1, t2)
        print(f"{score:.1f}% - '{t1}' vs '{t2}'")
