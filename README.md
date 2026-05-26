# Newsmash

Fetches RSS feeds from 10 UK news outlets across the political spectrum, clusters stories that cover the same event, then uses Claude to write an unbiased summary and analyse how each outlet frames the story differently.

The first request each day hits the feeds and Claude (~10 API calls). Everything after that is served from a date-keyed cache — so it costs the same whether one person reads it or a thousand.

## Hosting with Docker

### Prerequisites

- Docker and Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)

### Start

```bash
ANTHROPIC_API_KEY=sk-ant-... docker compose up -d
```

Open **http://localhost**.

The first page load will take up to 30 seconds while it fetches feeds and calls Claude. Subsequent loads are instant.

### Stop

```bash
docker compose down
```

The daily cache is stored in a Docker volume (`newsmash_cache`) so it survives restarts.

### Updating

```bash
git pull
docker compose up -d --build
```

## Running locally (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
uvicorn app.main:app --reload
```

Open **http://localhost:8000**.

## Sources

| Outlet | Lean |
|---|---|
| The Guardian | left |
| BBC News | centre-left |
| The Independent | centre-left |
| Reuters UK | centre |
| i Paper | centre |
| The Times | centre-right |
| The Telegraph | centre-right |
| Daily Mail | right |
| Daily Express | right |
| The Spectator | right |

## Configuration

| Env var | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `MAX_CLUSTERS` | `10` | Number of top stories to synthesise per day |
| `CLUSTER_SIMILARITY_THRESHOLD` | `0.25` | TF-IDF cosine similarity threshold for grouping stories |
| `FEED_TIMEOUT_SECONDS` | `10` | Per-feed fetch timeout |
