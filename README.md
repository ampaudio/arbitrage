# Sports Arbitrage Monitor

Real-time sports betting odds comparison between Polymarket and Kalshi.

## Deploy to Render.com (Free)

1. Push this folder to GitHub
2. Go to https://render.com and sign up
3. Click "New" -> "Web Service"
4. Connect your GitHub repo
5. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
6. Click "Create Web Service"

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:8001
