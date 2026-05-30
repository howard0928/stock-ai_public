# Stock AI

Generates a simple HTML email report for positions in `holdings.csv` that moved more than 5% during the latest daily trading session.

It also includes a local Streamlit app for personal portfolio journaling and Chinese trading review reports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
cp .env.example .env
```

Add your `FINNHUB_API_KEY` and `OPENAI_API_KEY` to `.env`.

## Holdings File

`holdings.csv` must include:

```csv
ticker,shares
AAPL,24
MSFT,12
```

## Run

### Large-move email report

```bash
stock-ai-report --holdings holdings.csv --output report.html
```

Or:

```bash
python -m stock_ai.cli --holdings holdings.csv --output report.html
```

Options:

- `--threshold 5`: percent move threshold.
- `--news-days 3`: lookback window for Finnhub company news.
- `--max-news 5`: maximum news articles summarized per moved holding.
- `--dry-run`: skip Finnhub and OpenAI calls and render a market-only report.

The generated `report.html` is ready to paste into an email client or send through your own email delivery system.

If no holding moves beyond the threshold, the report is generated immediately after the yfinance check and Finnhub/OpenAI are not called.

### Local portfolio journal app

```bash
streamlit run src/stock_ai/app.py
```

The app stores local portfolio data in SQLite. By default it uses:

```text
portfolio_journal.sqlite3
```

## Portfolio Journal Workflow

### Initialize a portfolio snapshot

1. Open the Streamlit app.
2. Go to "创建初始投资组合快照".
3. Enter the snapshot date, name, note, and each holding's ticker, shares, average cost, and initial thesis.
4. Click "保存初始快照".

This creates the starting portfolio. Later trades are applied on top of this snapshot.

### Add trades

Use "Button 2: Add latest trade" in the app.

Each trade records:

- trade datetime
- ticker
- buy or sell
- shares
- price
- fees
- trade reason
- confidence level
- intended holding period
- risk note

Buys increase shares and recalculate average cost. Sells decrease shares and record realized gain/loss. Selling more shares than currently held is rejected.

### Generate a review report

Use "Button 3: Generate review report" in the app.

The report is a concise Chinese trading review. It focuses on:

- current holdings
- the latest 5 trades
- current prices
- performance after each recent trade
- SPY or QQQ comparison
- Finnhub news when available
- key behavioral issues and next actions

If news or market data is missing, the report says `no reliable news found` or `data unavailable` instead of inventing information.

## API Keys

The existing `.env` loading style is used. Add these values to `.env`:

```text
FINNHUB_API_KEY=your_finnhub_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

The journal app uses Finnhub for news when available. The existing large-move report uses Finnhub and OpenAI when it is not run in dry-run mode.

This project is for personal investment review and learning. It does not provide financial advice and does not place trades automatically.
