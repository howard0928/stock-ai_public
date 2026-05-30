# Project Instructions

This is a personal AI stock portfolio analysis and trading review app.

## Existing Feature

- The existing large-move detection and report generation feature already works. Do not rewrite it unless explicitly asked.
- Prefer small, surgical changes.
- Do not refactor or reorganize working code unless the user explicitly asks for it.

## Environment Variables and API Keys

- Preserve the existing `.env` loading style.
- Never hard-code API keys.
- Use the existing `FINNHUB_API_KEY` and `OPENAI_API_KEY` variables from `.env`.
- If new environment variables are needed, update `.env.example`, not the real `.env`.

## Market Data and Report Integrity

- Do not fabricate market data, news, financial metrics, analyst revisions, or earnings information.
- If data is missing, show "data unavailable" or "no reliable news found".
- Separate facts, assumptions, and suggestions in generated reports.
- Reports should be written in Chinese.
- This tool is for personal investment review and learning, not financial advice.
- Do not make trading decisions automatically.
- Do not add brokerage trading or auto-order functionality.

## Code Organization

- Keep database logic, market-data fetching, and report-generation logic separated.
- Use SQLite for local persistent storage unless there is already a better existing storage pattern.

## UI Design

- When modifying or building the UI for this AI stock portfolio project, use the installed `frontend-design` skill if available.
- Use the `Industrial` anchor by default for this project's UI.
- Reason: this app is a data-heavy personal stock portfolio and trading review tool. The UI should feel like a clean trading terminal: dense, readable, serious, and focused on numbers.
- For UI redesign tasks in this project, use the installed `taste-skill` only when it is helpful.
- Prefer `redesign-existing-projects` from `taste-skill` for improving the existing app UI.
- Use `taste-skill` to audit and improve layout, spacing, visual hierarchy, typography, component polish, and responsive behavior.
- Do not use landing-page-oriented rules when they conflict with this app's needs.
- Use a dark trading-terminal style.
- Prefer monospace typography for tables, numbers, and dashboard elements.
- Use one clear semantic signal color system for positive, negative, warning, and neutral states.
- Keep tables readable and compact.
- Use strong alignment and tabular numerics.
- Avoid decorative UI that makes financial data harder to read.
- This app is a stock portfolio dashboard and trading review tool. It is data-heavy and table-heavy.
- Usability, readability, and correctness are more important than visual novelty.
- Do not make the app look like a marketing landing page.
- Do not hide important data behind decorative UI.
- Do not use fake tickers, fake prices, fake news, fake metrics, or fake analyst data just to make the UI look complete.
- If data is missing, show an empty state or "data unavailable".
- Standard actions should use standard labels, such as "Add trade", "Generate review", and "Check large moves".
- Keep the three main actions clear and not crowded: "Check large moves", "Add latest trade", and "Generate review report".
- Do not use overly playful, chaotic, or decorative anchors for this project unless the user explicitly asks.
- Do not change business logic while doing UI redesign unless explicitly asked.
- Do not rewrite the existing large-move detection feature while doing UI redesign.

## Communication

- When reporting back to the user, use simple, direct language and avoid unnecessary technical jargon.
