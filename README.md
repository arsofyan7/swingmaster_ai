<div align="center">
  <h1>📈 SwingMaster AI</h1>
  <p><i>A smart, AI-powered stock & forex screening, portfolio management, and advanced technical analysis platform.</i></p>
</div>

---

## 🌟 Overview

**SwingMaster AI** is a comprehensive full-stack platform tailored for traders and investors in the **Indonesian Stock Exchange (IDX)** and **Global Forex/Gold Markets**. It combines raw market data, psychological trading tags, strict algorithmic technical strategies (Smart Money Concepts), and cutting-edge **Google Gemini** AI capabilities. The result is an all-in-one actionable dashboard to automate analysis, receive real-time alerts, and track your portfolios—delivered through a sleek, modern, dark-mode Single Page Application (SPA).

---

## 🚀 Key Features

* **🤖 AI-Powered Technical Analysis:** Integrates with Google Gemini to automatically generate comprehensive technical analysis, summaries, and risk/reward calculations based on historical OHLCV data.
* **🧠 Smart Money Concepts (SMC) Engine:** Built-in algorithmic engine to detect advanced price action patterns including **Break of Structure (BOS)**, **Change of Character (CHoCH)**, and **Fair Value Gaps (FVG)** across multiple timeframes.
* **🌍 Multi-Market Support:** Dedicated support for both **Saham Lokal (IDX)** and **Forex/Gold (XAUUSD, EURUSD, GBPUSD, etc.)**, with separate dashboards and widgets.
* **📱 Telegram Bot Integration:** Get instant notifications pushed directly to your Telegram! Features Daily End-of-Day (EOD) alerts and **Hourly (H1) SMC Alerts** for both Stocks and Forex.
* **💼 Multi-Portfolio Management:** Create and manage multiple distinct portfolios (categorized by Stocks or Forex). Features real-time tracking, live PnL calculations, cascading data deletion, and risk-per-trade parameters.
* **📓 Trading Journal:** Automatically logs executed trades, complete with customizable psychological tags (e.g., "FOMO", "Disiplin Sesuai Plan"), R-Multiple calculations, and exportable data.
* **📈 Interactive Charts:** Integrated **TradingView Lightweight Charts** for smooth, on-the-fly technical charting right inside your browser.

---

## 🛠️ Technology Stack

**Backend:**
* [FastAPI](https://fastapi.tiangolo.com/) - Lightning-fast Python web framework
* [SQLite](https://www.sqlite.org/) - Lightweight, serverless relational database (`market_data.db`)
* [Google Generative AI SDK](https://ai.google.dev/) - For Gemini 3.5 Flash integration
* `yfinance` & `pandas` - For reliable market data retrieval and algorithmic calculations
* `schedule` - For automated hourly/daily background cron tasks

**Frontend:**
* Vanilla JavaScript (Identity-Driven SPA architecture)
* HTML5 & [Tailwind CSS](https://tailwindcss.com/)
* [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)

---

## ⚙️ Installation & Setup

Follow these steps to get the project running locally:

### 1. Clone the repository
```bash
git clone https://github.com/arsofyan7/swingmaster_ai.git
cd swingmaster_ai/backend
```

### 2. Set up the Python Environment
Ensure you have Python 3.9+ installed. It is recommended to use a virtual environment.
```bash
python -m venv env

# On Windows:
env\Scripts\activate
# On Linux/Mac/WSL:
source env/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` in the `backend` directory and fill in your API keys and credentials:
```env
# backend/.env
GEMINI_API_KEY=your_gemini_api_key_here
JWT_SECRET=your_secure_jwt_secret_here

# Telegram Bot Integration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 5. Run the Server
Use the custom runner script which handles database migrations and starts background schedulers (for Telegram hourly alerts) alongside the web server:
```bash
python run.py
```
*The API will be available at `http://127.0.0.1:8000`.*
*The Frontend SPA is automatically served at the root URL: `http://127.0.0.1:8000/`.*

---

## 💡 Usage Highlights

1. **Authentication:** Create a secure local account to isolate your portfolios and journals.
2. **Dashboard:** Monitor IHSG/Forex trends, open active positions, and overall portfolio equity. Easily switch between multiple portfolios from the top header or the Profile tab.
3. **Screener & Alerts:** 
   - View automated AI analysis results in the **Screener**.
   - Check the **Alerts** tab to see generated trading signals, complete with Entry, TP, and SL targets.
   - Use the "Test Telegram" button to verify your bot integration.
4. **Action Menu:** Click on any stock/pair ticker anywhere in the app to immediately view its interactive chart, read its latest AI diagnosis, or add it to your Watchlist.
5. **Profile & Management:** Configure risk settings per portfolio, review account settings, or manage/delete entire portfolios natively.

---

## 🔒 Secure Coding Practices
This project adheres to [secure coding guidelines](secure_coding.md), ensuring that:
- API keys, JWT secrets, and Telegram tokens are never hardcoded.
- Input validation is strictly typed via Pydantic on the backend.
- Password hashing uses modern `bcrypt` algorithms via Passlib.
- Endpoints are protected by rate limiters and JWT authentication.

---

<div align="center">
  <p>Built with ❤️ by <a href="https://github.com/arsofyan7">arsofyan7</a></p>
</div>
