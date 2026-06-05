# Stock AI Portfolio Journal

A local-first AI stock portfolio journal and trading review tool.

It has two main workflows:

- Check current holdings for large daily price moves and generate a readable HTML report.
- Keep a local portfolio journal in SQLite and generate concise Chinese trading review reports.

The app is designed for personal investment review and learning. It does not provide financial advice, does not connect to a brokerage account, and does not place trades automatically.

## Privacy Model

This project is intended to run locally.

Do not commit or share your personal files:

- `.env`
- `portfolio_journal.sqlite3`
- `holdings.csv`
- `report.html`
- `portfolio_review.md`
- screenshots of brokerage accounts
- exported transaction history

These files are ignored by `.gitignore`. API keys should only be stored in your local `.env` file.

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

Use your own local file. Do not publish real holdings if you share this project publicly.

## Run

### Large-move report

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

The generated `report.html` can be opened locally or downloaded from the Streamlit app.

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
2. Open `Initial portfolio snapshot`.
3. Enter the snapshot date, name, note, and each holding's ticker, shares, average cost, and initial thesis.
4. Save the snapshot.

This creates the starting portfolio. Later trades are applied on top of this snapshot.

### Add trades

Use `Add latest trade` in the app.

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

Use `Generate review report` in the app.

The report is a concise Chinese trading review. It focuses on:

- current holdings
- the latest 5 trades, grouped by same-day same-ticker activity
- current prices
- performance after each recent trade
- SPY or QQQ comparison
- relevant Finnhub news when available
- key behavioral issues and next actions

If news or market data is missing, the app avoids fabricating information. Missing data is either omitted or shown as `data unavailable` only when necessary.

## UI

The Streamlit app uses a dark trading-terminal style optimized for tables, portfolio metrics, and Chinese review reports. Large-move reports and trading review reports open in a separate dialog with download buttons, so generated output does not crowd the main dashboard.

## API Keys

The existing `.env` loading style is used. Add these values to `.env`:

```text
FINNHUB_API_KEY=your_finnhub_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

The journal app uses Finnhub for news when available. The existing large-move report uses Finnhub and OpenAI when it is not run in dry-run mode.

## Data Sources

- yfinance: prices and basic market/fundamental fields.
- Finnhub: market and company news.
- OpenAI API: summarization and report generation.

Market data and news availability can vary by ticker and provider. The app should not fabricate market data, news, financial metrics, analyst revisions, or earnings information.

## Disclaimer

This project is for personal investment review and learning only. It is not financial advice.
