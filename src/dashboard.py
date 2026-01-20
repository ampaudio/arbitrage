"""
Arbitrage Dashboard - Web interface for monitoring arbitrage opportunities

Flask application that displays:
- Real-time spread monitoring between Polymarket and Kalshi
- Price convergence charts
- Alert notifications for high-spread opportunities
- Auto-refresh every 30 seconds
"""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict

from flask import Flask, render_template_string, request, jsonify

from .polymarket import PolymarketClient
from .kalshi import KalshiClient
from .matcher import MarketMatcher
from .arbitrage import ArbitrageCalculator, ArbitrageOpportunity

app = Flask(__name__)

# Global state for caching
_cache = {
    'opportunities': [],
    'last_fetch': None,
    'history': [],
    'alerts': [],
}

CACHE_TTL_SECONDS = 30


def fetch_opportunities(force_refresh: bool = False) -> List[ArbitrageOpportunity]:
    """Fetch and calculate arbitrage opportunities with parallel API calls."""
    global _cache
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    
    now = datetime.now(timezone.utc)
    
    # Use cache if fresh
    if not force_refresh and _cache['last_fetch']:
        age = (now - _cache['last_fetch']).total_seconds()
        if age < CACHE_TTL_SECONDS:
            return _cache['opportunities']
    
    # Fetch both APIs in parallel for speed
    poly_markets = []
    kalshi_markets = []
    
    def fetch_poly():
        client = PolymarketClient(timeout=10)  # Shorter timeout
        return client.get_simplified_markets()
    
    def fetch_kalshi():
        client = KalshiClient(timeout=10)  # Shorter timeout
        return client.get_simplified_markets()
    
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            poly_future = executor.submit(fetch_poly)
            kalshi_future = executor.submit(fetch_kalshi)
            
            # Wait max 15 seconds for both
            try:
                poly_markets = poly_future.result(timeout=15)
            except:
                poly_markets = []
            
            try:
                kalshi_markets = kalshi_future.result(timeout=15)
            except:
                kalshi_markets = []
    except Exception as e:
        print(f"Error in parallel fetch: {e}")
    
    # Match markets
    matcher = MarketMatcher(similarity_threshold=60.0)  # Slightly lower for more matches
    matches = matcher.find_matches(kalshi_markets, poly_markets)
    
    # Calculate spreads
    calculator = ArbitrageCalculator(min_spread_pct=0.5)
    opportunities = calculator.find_opportunities(matches)
    
    # Update cache
    _cache['opportunities'] = opportunities
    _cache['last_fetch'] = now
    
    # Track history for charts
    if opportunities:
        _cache['history'].append({
            'timestamp': now.isoformat(),
            'top_spread': opportunities[0].spread_pct if opportunities else 0,
            'count': len(opportunities),
        })
        # Keep last 100 history points
        _cache['history'] = _cache['history'][-100:]
    
    # Check for alerts
    for opp in opportunities:
        if opp.spread_pct >= 3.0:  # Alert threshold
            alert = {
                'timestamp': now.isoformat(),
                'spread': opp.spread_pct,
                'title': opp.kalshi_title,
                'type': 'HIGH_OPPORTUNITY',
            }
            _cache['alerts'].append(alert)
            _cache['alerts'] = _cache['alerts'][-50:]  # Keep last 50 alerts
    
    return opportunities


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'X ago' string."""
    if not dt:
        return "Never"
    
    now = datetime.now(timezone.utc)
    delta = now - dt
    
    if delta.total_seconds() < 60:
        return f"{int(delta.total_seconds())}s ago"
    elif delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() / 60)}m ago"
    else:
        return f"{int(delta.total_seconds() / 3600)}h ago"


DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>POLARLYST ARB MONITORING</title>
    <style>
        :root {
            --bg-primary: #f8f9fc;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f0f4f8;
            --text-primary: #1a202c;
            --text-secondary: #64748b;
            --accent: #10b981;
            --accent-light: rgba(16, 185, 129, 0.1);
            --warning: #f59e0b;
            --danger: #ef4444;
            --border: #e2e8f0;
            --shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
            --radius: 16px;
        }
        
        [data-theme="dark"] {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --border: #334155;
            --shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #e8f5e9 0%, #f5f5dc 50%, #fff8e1 100%);
            min-height: 100vh;
            color: var(--text-primary);
        }
        
        [data-theme="dark"] body {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Top Bar */
        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 24px;
            background: var(--bg-secondary);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            margin-bottom: 24px;
        }
        
        .brand {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            font-size: 18px;
        }
        
        .brand-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--accent), #059669);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        
        .time-tabs {
            display: flex;
            gap: 4px;
            background: var(--bg-tertiary);
            padding: 4px;
            border-radius: 8px;
        }
        
        .time-tab {
            padding: 8px 16px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
        }
        
        .time-tab.active, .time-tab:hover {
            background: var(--bg-secondary);
            color: var(--text-primary);
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .topbar-actions {
            display: flex;
            gap: 12px;
        }
        
        .btn {
            padding: 10px 20px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-primary);
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .btn:hover {
            border-color: var(--accent);
            color: var(--accent);
        }
        
        /* Main Card */
        .main-card {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            overflow: hidden;
            margin-bottom: 24px;
        }
        
        .card-header {
            padding: 24px;
            border-bottom: 1px solid var(--border);
            position: relative;
        }
        
        .event-label {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }
        
        .event-title {
            font-size: 15px;
            font-weight: 500;
            color: var(--text-primary);
        }
        
        .badges {
            position: absolute;
            right: 24px;
            top: 20px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            align-items: flex-end;
        }
        
        .badge {
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .badge-opportunity {
            background: var(--accent);
            color: white;
        }
        
        .badge-neutral {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }
        
        .badge-warning {
            background: var(--warning);
            color: white;
        }
        
        .badge-bookmarked {
            background: #3b82f6;
            color: white;
            transform: rotate(45deg);
            position: absolute;
            right: -30px;
            top: 15px;
            width: 100px;
            text-align: center;
        }
        
        /* Spread Display */
        .spread-section {
            padding: 32px;
            text-align: center;
            background: linear-gradient(180deg, var(--accent-light) 0%, transparent 100%);
        }
        
        .spread-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .spread-value {
            font-size: 64px;
            font-weight: 700;
            color: var(--accent);
            line-height: 1;
        }
        
        .spread-value.negative {
            color: var(--danger);
        }
        
        /* Chart Section */
        .chart-section {
            padding: 24px;
            border-top: 1px solid var(--border);
        }
        
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        
        .chart-title {
            font-size: 14px;
            font-weight: 600;
        }
        
        .chart-legend {
            display: flex;
            gap: 16px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .legend-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .chart-container {
            height: 200px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        
        .chart-placeholder {
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        /* SVG Chart */
        .price-chart {
            width: 100%;
            height: 100%;
        }
        
        /* Action Panel */
        .action-panel {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 24px;
            margin-bottom: 24px;
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .panel-title {
            font-size: 14px;
            font-weight: 600;
        }
        
        .status-badge {
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            background: var(--accent);
            color: white;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .stat-box {
            padding: 16px;
            background: var(--bg-tertiary);
            border-radius: 12px;
        }
        
        .stat-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .stat-value.green {
            color: var(--accent);
        }
        
        /* Progress Bar */
        .progress-section {
            margin-bottom: 20px;
        }
        
        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        
        .progress-label {
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .progress-bar {
            height: 6px;
            background: var(--bg-tertiary);
            border-radius: 3px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent), #059669);
            border-radius: 3px;
            transition: width 0.3s ease;
        }
        
        /* Current Spread Box */
        .current-spread-box {
            background: var(--bg-tertiary);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .current-spread-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        
        .current-spread-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--accent);
        }
        
        /* Replay Button */
        .replay-btn {
            width: 100%;
            padding: 16px;
            background: var(--text-primary);
            color: var(--bg-secondary);
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s;
        }
        
        .replay-btn:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        
        /* Opportunities Table */
        .opportunities-card {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            overflow: hidden;
        }
        
        .opportunities-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .opportunities-title {
            font-size: 16px;
            font-weight: 600;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 16px 24px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: var(--bg-tertiary);
        }
        
        td {
            font-size: 14px;
        }
        
        .market-title {
            font-weight: 500;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .market-link {
            color: var(--accent);
            text-decoration: none;
        }
        
        .market-link:hover {
            text-decoration: underline;
        }
        
        .price-cell {
            font-weight: 600;
            font-family: 'SF Mono', 'Menlo', monospace;
        }
        
        .spread-cell {
            font-weight: 700;
            color: var(--accent);
            font-family: 'SF Mono', 'Menlo', monospace;
        }
        
        .spread-cell.low {
            color: var(--text-secondary);
        }
        
        .match-score {
            display: inline-block;
            padding: 4px 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 12px;
        }
        
        /* Alerts */
        .alert-banner {
            background: linear-gradient(90deg, var(--accent), #059669);
            color: white;
            padding: 12px 24px;
            border-radius: var(--radius);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        
        .alert-icon {
            font-size: 20px;
        }
        
        .alert-text {
            flex: 1;
            font-weight: 500;
        }
        
        .alert-dismiss {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
        }
        
        /* Auto-refresh indicator */
        .refresh-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .refresh-dot {
            width: 8px;
            height: 8px;
            background: var(--accent);
            border-radius: 50%;
            animation: blink 2s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 16px;
            }
            
            .topbar {
                flex-wrap: wrap;
                gap: 12px;
            }
            
            .spread-value {
                font-size: 48px;
            }
            
            .stats-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Top Bar -->
        <div class="topbar">
            <div class="brand">
                <div class="brand-icon">P</div>
                <span>POLARLYST ARB MONITORING</span>
            </div>
            
            <div class="time-tabs">
                <button class="time-tab active">1W</button>
                <button class="time-tab">1M</button>
                <button class="time-tab">3M</button>
                <button class="time-tab">ALL</button>
            </div>
            
            <div class="topbar-actions">
                <button class="btn" onclick="copyLink()">📋 COPY LINK</button>
                <button class="btn" onclick="toggleConfig()">⚙️ CONFIG (CTRL/CMD+K)</button>
            </div>
        </div>
        
        <!-- Alert Banner (if high opportunity) -->
        {% if top_opportunity and top_opportunity.spread_pct >= 3.0 %}
        <div class="alert-banner">
            <span class="alert-icon">🚀</span>
            <span class="alert-text">HIGH OPPORTUNITY DETECTED: {{ top_opportunity.kalshi_title[:60] }}... (+{{ "%.2f"|format(top_opportunity.spread_pct) }}%)</span>
            <button class="alert-dismiss">Dismiss</button>
        </div>
        {% endif %}
        
        <!-- Main Card -->
        <div class="main-card">
            <div class="card-header">
                <div class="event-label">EVENT: {{ top_opportunity.kalshi_title if top_opportunity else 'No opportunities found' }}</div>
                <div class="event-title">{{ top_opportunity.polymarket_title if top_opportunity else 'Waiting for data...' }}</div>
                
                <div class="badges">
                    {% if top_opportunity and top_opportunity.spread_pct >= 3.0 %}
                    <span class="badge badge-opportunity">HIGH OPPORTUNITY</span>
                    {% elif top_opportunity %}
                    <span class="badge badge-neutral">MONITORING</span>
                    {% endif %}
                    <span class="badge badge-neutral">DELTA NEUTRAL</span>
                    <span class="badge badge-neutral">SPREAD COMPRESSION</span>
                </div>
            </div>
            
            <div class="spread-section">
                <div class="spread-label">CURRENT SPREAD</div>
                <div class="spread-value {% if not top_opportunity or top_opportunity.spread_pct < 0 %}negative{% endif %}">
                    +{{ "%.2f"|format(top_opportunity.spread_pct if top_opportunity else 0) }}%
                </div>
            </div>
            
            <div class="chart-section">
                <div class="chart-header">
                    <div class="chart-title">PRICE CONVERGENCE</div>
                    <div class="chart-legend">
                        <span class="legend-item"><span class="legend-dot" style="background: #3b82f6;"></span> Polymarket YES</span>
                        <span class="legend-item"><span class="legend-dot" style="background: #10b981;"></span> Kalshi YES</span>
                        <span class="legend-item"><span class="legend-dot" style="background: #f59e0b;"></span> Spread</span>
                    </div>
                </div>
                <div class="chart-container">
                    {% if history|length > 1 %}
                    <svg class="price-chart" viewBox="0 0 800 180" preserveAspectRatio="none">
                        <!-- Grid lines -->
                        <line x1="0" y1="45" x2="800" y2="45" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4"/>
                        <line x1="0" y1="90" x2="800" y2="90" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4"/>
                        <line x1="0" y1="135" x2="800" y2="135" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4"/>
                        
                        <!-- Spread line -->
                        <polyline 
                            fill="none" 
                            stroke="#f59e0b" 
                            stroke-width="2"
                            points="{% for i, h in enumerate(history[-20:]) %}{{ (i * 40) }},{{ 160 - (h.top_spread * 10) }} {% endfor %}"
                        />
                        
                        <!-- Data points -->
                        {% for i, h in enumerate(history[-20:]) %}
                        <circle cx="{{ i * 40 }}" cy="{{ 160 - (h.top_spread * 10) }}" r="4" fill="#f59e0b"/>
                        {% endfor %}
                    </svg>
                    {% else %}
                    <span class="chart-placeholder">📊 Chart data will appear after multiple data points</span>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- Action Panel -->
        <div class="action-panel">
            <div class="panel-header">
                <span class="panel-title">ACTION PANEL</span>
                <span class="status-badge">{{ 'PROFITABLE' if profitable_count > 0 else 'MONITORING' }}</span>
            </div>
            
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">OPPORTUNITIES FOUND</div>
                    <div class="stat-value">{{ opportunities_count }}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">PROFITABLE (>2%)</div>
                    <div class="stat-value green">{{ profitable_count }}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">AVG SPREAD</div>
                    <div class="stat-value">{{ "%.2f"|format(avg_spread) }}%</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">LAST UPDATED</div>
                    <div class="stat-value" style="font-size: 16px;">{{ last_updated }}</div>
                </div>
            </div>
            
            <div class="progress-section">
                <div class="progress-header">
                    <span class="progress-label">Markets Scanned Progress</span>
                    <span class="progress-label">{{ markets_scanned }} / {{ markets_scanned }}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 100%;"></div>
                </div>
            </div>
            
            <div class="current-spread-box">
                <div class="current-spread-label">CURRENT BEST SPREAD</div>
                <div class="current-spread-value">+{{ "%.2f"|format(max_spread) }}%</div>
            </div>
            
            <button class="replay-btn" onclick="refreshData()">
                ↻ REFRESH DATA
            </button>
        </div>
        
        <!-- Opportunities Table -->
        <div class="opportunities-card">
            <div class="opportunities-header">
                <span class="opportunities-title">🎯 Arbitrage Opportunities</span>
                <div class="refresh-indicator">
                    <span class="refresh-dot"></span>
                    <span>LIVE DATA • AUTO-REFRESHES EVERY 30S</span>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Market</th>
                        <th>Polymarket</th>
                        <th>Kalshi</th>
                        <th>Spread</th>
                        <th>Match</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for opp in opportunities[:20] %}
                    <tr>
                        <td>
                            <div class="market-title">{{ opp.kalshi_title[:50] }}{% if opp.kalshi_title|length > 50 %}...{% endif %}</div>
                        </td>
                        <td class="price-cell">
                            YES: {{ "%.0f"|format(opp.polymarket_yes * 100) }}¢<br>
                            <span style="color: var(--text-secondary);">NO: {{ "%.0f"|format(opp.polymarket_no * 100) }}¢</span>
                        </td>
                        <td class="price-cell">
                            YES: {{ "%.0f"|format(opp.kalshi_yes * 100) }}¢<br>
                            <span style="color: var(--text-secondary);">NO: {{ "%.0f"|format(opp.kalshi_no * 100) }}¢</span>
                        </td>
                        <td class="spread-cell {% if opp.spread_pct < 2 %}low{% endif %}">
                            +{{ "%.2f"|format(opp.spread_pct) }}%
                        </td>
                        <td>
                            <span class="match-score">{{ "%.0f"|format(opp.similarity) }}%</span>
                        </td>
                        <td>
                            <a href="{{ opp.polymarket_url }}" target="_blank" class="market-link">Poly</a> |
                            <a href="{{ opp.kalshi_url }}" target="_blank" class="market-link">Kalshi</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                            No arbitrage opportunities found. Markets are efficiently priced! 📈
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            LIVE DATA • AUTO-REFRESHES EVERY 30S
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => {
            window.location.reload();
        }, 30000);
        
        function refreshData() {
            window.location.href = '/?refresh=1';
        }
        
        function copyLink() {
            navigator.clipboard.writeText(window.location.href);
            alert('Link copied to clipboard!');
        }
        
        function toggleConfig() {
            alert('Config panel coming soon!');
        }
        
        // Dark mode toggle with keyboard shortcut
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const html = document.documentElement;
                const current = html.getAttribute('data-theme');
                html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
                localStorage.setItem('theme', html.getAttribute('data-theme'));
            }
        });
        
        // Load saved theme
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
        }
    </script>
</body>
</html>
'''


@app.route('/')
def dashboard():
    """Main dashboard route."""
    force_refresh = request.args.get('refresh') == '1'
    opportunities = fetch_opportunities(force_refresh=force_refresh)
    
    # Prepare template data
    top_opportunity = opportunities[0] if opportunities else None
    profitable = [o for o in opportunities if o.is_profitable()]
    spreads = [o.spread_pct for o in opportunities] if opportunities else [0]
    
    return render_template_string(
        DASHBOARD_TEMPLATE,
        opportunities=[o.to_dict() for o in opportunities],
        top_opportunity=top_opportunity,
        opportunities_count=len(opportunities),
        profitable_count=len(profitable),
        avg_spread=sum(spreads) / len(spreads) if spreads else 0,
        max_spread=max(spreads) if spreads else 0,
        markets_scanned=len(opportunities),
        last_updated=format_time_ago(_cache['last_fetch']),
        history=_cache['history'],
        enumerate=enumerate,
    )


@app.route('/api/opportunities')
def api_opportunities():
    """API endpoint for opportunities data."""
    force_refresh = request.args.get('refresh') == '1'
    opportunities = fetch_opportunities(force_refresh=force_refresh)
    
    return jsonify({
        'opportunities': [o.to_dict() for o in opportunities],
        'count': len(opportunities),
        'last_updated': _cache['last_fetch'].isoformat() if _cache['last_fetch'] else None,
    })


@app.route('/api/alerts')
def api_alerts():
    """API endpoint for alerts."""
    return jsonify({
        'alerts': _cache['alerts'],
    })


def run_dashboard(host: str = '127.0.0.1', port: int = 8001, debug: bool = False):
    """Run the dashboard server."""
    print(f"\n>>> Starting Arbitrage Monitor Dashboard")
    print(f"    Open http://{host}:{port} in your browser\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_dashboard(debug=True)
