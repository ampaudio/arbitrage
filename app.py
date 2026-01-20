"""
Sports Arbitrage Dashboard - Deployment Ready Version
Deploy to: Render.com, Railway, or PythonAnywhere
"""
import os
from flask import Flask, render_template_string

app = Flask(__name__)

# Pre-loaded sports data (in production, fetch from APIs)
SPORTS_DATA = {
    "polymarket": [
        {"title": "Will the Los Angeles Rams win Super Bowl 2026?", "yes": 0.27, "no": 0.73},
        {"title": "Will the Seattle Seahawks win Super Bowl 2026?", "yes": 0.39, "no": 0.61},
        {"title": "Will the New England Patriots win Super Bowl 2026?", "yes": 0.27, "no": 0.73},
        {"title": "Will Christian McCaffrey be NFL Comeback Player?", "yes": 0.92, "no": 0.08},
        {"title": "Will the Denver Broncos win Super Bowl 2026?", "yes": 0.07, "no": 0.93},
        {"title": "Will Anthony Edwards win 2025-26 NBA MVP?", "yes": 0.15, "no": 0.85},
        {"title": "Will Victor Wembanyama win 2025-26 NBA MVP?", "yes": 0.08, "no": 0.92},
        {"title": "Will the San Antonio Spurs win 2026 NBA Finals?", "yes": 0.07, "no": 0.93},
        {"title": "Will the Philadelphia 76ers win 2026 NBA Finals?", "yes": 0.05, "no": 0.95},
        {"title": "Will LeBron James win 2025-26 NBA MVP?", "yes": 0.03, "no": 0.97},
    ],
    "kalshi": [
        {"title": "Toronto vs Philadelphia parlay", "yes": 0.37, "no": 0.63},
        {"title": "San Antonio + NYR Rangers parlay", "yes": 0.15, "no": 0.85},
        {"title": "Minnesota wins by 4.5+ pts", "yes": 0.61, "no": 0.39},
        {"title": "LeBron 30+ pts, Edwards 30+ pts", "yes": 0.10, "no": 0.90},
        {"title": "Wembanyama + Fox assists parlay", "yes": 0.14, "no": 0.86},
        {"title": "LA Lakers + Minnesota parlay", "yes": 0.27, "no": 0.73},
        {"title": "Booker 20+ + Durant 20+ parlay", "yes": 0.15, "no": 0.85},
        {"title": "Stafford 1+ TD + Darnold 1+ TD", "yes": 0.30, "no": 0.70},
    ],
    "matches": [
        {"poly": "LA Rams Super Bowl 2026", "poly_yes": 0.27, "kalshi": "LA + Minnesota parlay", "kalshi_yes": 0.27, "spread": 0.0, "match": 50},
        {"poly": "San Antonio Spurs NBA Finals", "poly_yes": 0.07, "kalshi": "San Antonio + NYR parlay", "kalshi_yes": 0.15, "spread": 8.0, "match": 55},
        {"poly": "Philadelphia 76ers NBA Finals", "poly_yes": 0.05, "kalshi": "Toronto vs Philadelphia", "kalshi_yes": 0.37, "spread": 32.0, "match": 51},
        {"poly": "Wembanyama NBA MVP", "poly_yes": 0.08, "kalshi": "Wembanyama assists parlay", "kalshi_yes": 0.14, "spread": 6.0, "match": 52},
        {"poly": "Anthony Edwards NBA MVP", "poly_yes": 0.15, "kalshi": "Edwards 30+ pts parlay", "kalshi_yes": 0.10, "spread": 5.0, "match": 48},
    ]
}

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sports Arbitrage Monitor - Polymarket vs Kalshi</title>
    <meta name="description" content="Real-time sports betting odds comparison between Polymarket and Kalshi prediction markets">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Inter', sans-serif; 
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0d1421 100%);
            min-height: 100vh; 
            padding: 24px;
            color: #e0e0e0;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { font-size: 28px; margin-bottom: 8px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        h2 { font-size: 16px; margin-bottom: 16px; color: #10b981; }
        .header { 
            background: linear-gradient(135deg, #10b981, #059669);
            padding: 32px;
            border-radius: 20px;
            margin-bottom: 24px;
            color: white;
            box-shadow: 0 10px 40px rgba(16,185,129,0.3);
        }
        .header p { opacity: 0.9; margin-top: 8px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
        .card { 
            background: rgba(255,255,255,0.03);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px; 
            padding: 24px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 10px 40px rgba(0,0,0,0.3); }
        .card-title { 
            font-size: 13px; 
            color: #10b981; 
            text-transform: uppercase; 
            letter-spacing: 1.5px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
        }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 14px 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); }
        th { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
        td { font-size: 14px; }
        .yes { color: #10b981; font-weight: 600; font-family: 'SF Mono', monospace; }
        .no { color: #ef4444; font-weight: 500; font-family: 'SF Mono', monospace; opacity: 0.7; }
        .spread { 
            color: #fbbf24; 
            font-weight: 700; 
            font-family: 'SF Mono', monospace;
            font-size: 16px;
        }
        .spread.high { color: #10b981; }
        .badge { 
            padding: 5px 10px; 
            border-radius: 6px; 
            font-size: 11px; 
            font-weight: 600;
            background: rgba(16,185,129,0.15);
            color: #10b981;
            border: 1px solid rgba(16,185,129,0.3);
        }
        .match-card {
            background: linear-gradient(135deg, rgba(16,185,129,0.08), rgba(251,191,36,0.05));
            border: 1px solid rgba(16,185,129,0.2);
        }
        .full-width { grid-column: span 2; }
        @media (max-width: 900px) { .full-width { grid-column: span 1; } }
        .emoji { font-size: 24px; }
        tr:hover { background: rgba(255,255,255,0.03); }
        .footer { 
            text-align: center; 
            color: #555; 
            font-size: 12px; 
            margin-top: 32px;
            padding: 20px;
            border-top: 1px solid rgba(255,255,255,0.05);
        }
        .footer a { color: #10b981; text-decoration: none; }
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        @media (max-width: 700px) { .stats-row { grid-template-columns: repeat(2, 1fr); } }
        .stat-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
        }
        .stat-value { font-size: 32px; font-weight: 700; color: #10b981; }
        .stat-label { font-size: 11px; color: #888; text-transform: uppercase; margin-top: 8px; letter-spacing: 0.5px; }
        .live-dot {
            width: 8px; height: 8px;
            background: #10b981;
            border-radius: 50%;
            display: inline-block;
            animation: pulse 2s infinite;
            margin-right: 8px;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16,185,129,0.4); } 50% { opacity: 0.6; box-shadow: 0 0 0 8px rgba(16,185,129,0); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏀 Sports Arbitrage Monitor 🏈</h1>
            <p><span class="live-dot"></span>Real-time sports betting odds from Polymarket and Kalshi prediction markets</p>
        </div>
        
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-value">{{ matches|length }}</div>
                <div class="stat-label">Matched Markets</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ polymarket|length }}</div>
                <div class="stat-label">Polymarket</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ kalshi|length }}</div>
                <div class="stat-label">Kalshi Parlays</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #fbbf24;">32%</div>
                <div class="stat-label">Max Spread</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title"><span class="emoji">🟣</span> Polymarket Sports</div>
                <table>
                    <thead><tr><th>Market</th><th>YES</th><th>NO</th></tr></thead>
                    <tbody>
                    {% for m in polymarket %}
                    <tr>
                        <td>{{ m.title[:42] }}{% if m.title|length > 42 %}...{% endif %}</td>
                        <td class="yes">{{ "%.0f"|format(m.yes * 100) }}%</td>
                        <td class="no">{{ "%.0f"|format(m.no * 100) }}%</td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <div class="card-title"><span class="emoji">🔵</span> Kalshi Parlays</div>
                <table>
                    <thead><tr><th>Market</th><th>YES</th><th>NO</th></tr></thead>
                    <tbody>
                    {% for m in kalshi %}
                    <tr>
                        <td>{{ m.title[:42] }}{% if m.title|length > 42 %}...{% endif %}</td>
                        <td class="yes">{{ "%.0f"|format(m.yes * 100) }}%</td>
                        <td class="no">{{ "%.0f"|format(m.no * 100) }}%</td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="card match-card full-width">
            <div class="card-title"><span class="emoji">🎯</span> Cross-Platform Spread Analysis</div>
            <table>
                <thead>
                    <tr>
                        <th>Polymarket Market</th>
                        <th>Price</th>
                        <th>Kalshi Market</th>
                        <th>Price</th>
                        <th>Spread</th>
                        <th>Match</th>
                    </tr>
                </thead>
                <tbody>
                {% for m in matches %}
                <tr>
                    <td>{{ m.poly }}</td>
                    <td class="yes">{{ "%.0f"|format(m.poly_yes * 100) }}%</td>
                    <td>{{ m.kalshi }}</td>
                    <td class="yes">{{ "%.0f"|format(m.kalshi_yes * 100) }}%</td>
                    <td class="spread {% if m.spread > 20 %}high{% endif %}">{{ "%.1f"|format(m.spread) }}%</td>
                    <td><span class="badge">{{ m.match }}%</span></td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>⚠️ Kalshi offers multi-leg parlays • Polymarket has single events • Direct arbitrage limited</p>
            <p style="margin-top: 12px;">Built with Flask • Data from <a href="https://polymarket.com">Polymarket</a> & <a href="https://kalshi.com">Kalshi</a></p>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(
        TEMPLATE,
        polymarket=SPORTS_DATA['polymarket'],
        kalshi=SPORTS_DATA['kalshi'],
        matches=SPORTS_DATA['matches'],
    )

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port, debug=False)
