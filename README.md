<div align="center">
  <h1>📈 SwingMaster AI</h1>
  <p><i>A smart, AI-powered stock screening, portfolio management, and technical analysis platform.</i></p>
</div>

---

## 🌟 Overview

**SwingMaster AI** is a comprehensive full-stack platform tailored for stock traders and investors in the Indonesian Stock Exchange (IDX). It combines raw market data, psychological trading tags, and cutting-edge **Google Gemini** AI capabilities to provide actionable insights, automate technical analysis, and track portfolios—all from a sleek, dark-mode Single Page Application (SPA).

---

## 🚀 Key Features

* **🤖 AI-Powered Technical Analysis:** Integrates with Google Gemini to automatically generate comprehensive technical analysis and summaries based on historical OHLCV data.
* **📊 Interactive Stock Screener:** Filter, sort, and discover stocks using built-in composite indexes or custom criteria.
* **💼 Portfolio & Paper Trading Management:** Supports multiple portfolios, real-time tracking of active positions, live Profit/Loss calculations, and risk parameters (TP/SL).
* **📈 TradingView Charts:** Built-in interactive stock charts using Lightweight Charts to view OHLCV data on the fly.
* **📓 Trading Journal:** Automatically logs executed trades, complete with customizable psychological tags (e.g., "FOMO", "Disiplin Sesuai Plan") and exports to CSV.
* **📱 Responsive SPA UI:** A polished, modern, and mobile-responsive interface powered by Tailwind CSS.

---

## 🛠️ Technology Stack

**Backend:**
* [FastAPI](https://fastapi.tiangolo.com/) - Lightning-fast Python web framework
* [SQLite](https://www.sqlite.org/) - Lightweight, serverless relational database for local storage
* [Google Generative AI SDK](https://ai.google.dev/) - For Gemini 3.5 Flash integration

**Frontend:**
* Vanilla JavaScript (SPA architecture)
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
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
You will need a `.env` file in the `backend` directory with your Google Gemini API key and database path.
```env
# backend/.env
GEMINI_API_KEY=your_gemini_api_key_here
DB_PATH=swingmaster.db
```

### 5. Run the Server
```bash
uvicorn main:app --reload
```
*The API will be available at `http://127.0.0.1:8000`.*
*The Frontend SPA is automatically served at the root URL: `http://127.0.0.1:8000/`.*

---

## 💡 Usage Highlights

1. **Authentication:** Create an account or log in to manage your local state securely.
2. **Dashboard:** Monitor your IHSG trend, active positions, and portfolio summary. You can directly close positions or execute paper trades.
3. **Screening:** Navigate to the **Screener** tab to run AI batches on top index movers or custom watchlists.
4. **Action Menu:** Click on any stock ticker to immediately view the AI Technical Analysis chart, open an extended TradingView window, or add it to your Watchlist.

---

## 🔒 Secure Coding Practices
This project strictly adheres to [secure coding guidelines](secure_coding.md), ensuring that:
- API keys and sensitive tokens are never hardcoded.
- Input validation is rigorous on both client and server sides.
- State management and authentication avoid common XSS and CSRF pitfalls.

---

<div align="center">
  <p>Built with ❤️ by <a href="https://github.com/arsofyan7">arsofyan7</a></p>
</div>
