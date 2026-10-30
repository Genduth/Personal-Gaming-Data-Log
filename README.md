# GameVault

GameVault is a local-first gaming activity warehouse with a version-controlled Power BI dashboard. It backfills a Steam library and achievement history, watches games running on a PC, writes durable sessions to PostgreSQL, and exposes a DirectQuery semantic model for near-live reporting.

The project is intentionally personal-data friendly: your API keys and gaming history stay in infrastructure you control.

## What it tracks

- Steam library, lifetime playtime, recent playtime snapshots, profile data and achievement unlock timestamps
- Live PC game presence, session start/end time, device and executable
- Playtime patterns by date, weekday, hour, game and platform
- Achievement completion and global rarity
- Sync freshness, unmatched game processes and stale collector sessions

The Power BI project includes four pages:

1. **Overview** — currently playing, seven-day activity, lifetime hours, trend, favourite games and recent sessions
2. **Sessions & habits** — weekday/hour activity heatmap and session behaviour
3. **Achievements** — completion, rare unlocks and unlock history
4. **Data health** — source freshness, sync history and processes that still need mapping

## Architecture

```mermaid
flowchart LR
    Steam[Steam Web API] --> API[GameVault API]
    PC[Windows collector] -->|start / heartbeat / stop| API
    Imports[Future CSV / Playnite imports] --> API
    API --> DB[(PostgreSQL)]
    DB --> Views[Power BI views]
    Views -->|DirectQuery| PBI[Power BI report]
    API -. optional mirror .-> Fabric[Fabric Eventstream / Eventhouse]
    Fabric -. seconds-level .-> PBI
```

## Quick start

Requirements: Docker Desktop or Docker Engine, Python 3.12 on the gaming PC, and Power BI Desktop on Windows.

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD and COLLECTOR_TOKEN to long random values in .env.
docker compose up --build -d
curl http://localhost:8000/health
```

The API documentation is available at `http://localhost:8000/docs`.

### Backfill Steam

1. Create a Steam Web API key at <https://steamcommunity.com/dev/apikey>.
2. Put `STEAM_API_KEY` and your 64-bit `STEAM_ID` in `.env`.
3. Restart the API and run:

```bash
curl -X POST http://localhost:8000/v1/sync/steam \
  -H "Authorization: Bearer YOUR_COLLECTOR_TOKEN"
```

Steam provides lifetime totals and achievement unlock timestamps. It does not expose historical per-session timestamps, so GameVault starts building that higher-resolution history when the collector begins running. Every Steam sync stores a playtime snapshot, which lets the model calculate playtime deltas going forward.

### Start live PC tracking

After the Steam sync, map each game's executable. The game IDs are available in the `powerbi.games` view or the API database.

```bash
docker compose exec api gamevault add-alias GAME_UUID bg3.exe
```

On the gaming PC, run PowerShell as your normal user:

```powershell
.\collector\install-windows.ps1 `
  -ApiUrl "http://YOUR-SERVER:8000" `
  -Token "YOUR_COLLECTOR_TOKEN" `
  -DeviceName "Gaming-PC"
```

The collector uses only Python's standard library, starts at login, detects mapped executables every 15 seconds, sends a heartbeat every minute, and queues events locally while the server is offline.

### Open Power BI

Open [`powerbi/GameVault.pbip`](powerbi/GameVault.pbip) in Power BI Desktop. Set the `DatabaseHost` and `DatabaseName` Power Query parameters, authenticate with PostgreSQL, and keep the tables in DirectQuery mode. See [Power BI setup](docs/power-bi.md) for gateway, automatic page refresh and Fabric options.

## Development

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
ruff check .
pytest
```

Database migrations run automatically when the API container starts. Apply them manually with `gamevault migrate`.

## Repository map

| Path | Purpose |
| --- | --- |
| `powerbi/` | PBIP report and TMDL semantic model for source control |
| `src/gamevault/` | FastAPI ingestion API, Steam sync and CLI |
| `collector/` | Cross-platform process collector and Windows scheduled-task installer |
| `database/migrations/` | PostgreSQL warehouse schema and Power BI views |
| `docs/` | Architecture, Power BI deployment, data sources and roadmap |
| `tests/` | Collector, database and PBIP structure tests |

## Current source coverage

Steam and PC process tracking are implemented. PlayStation and Xbox do not offer equivalent open, stable APIs for personal telemetry; the roadmap therefore uses supported exports, Playnite ingestion and optional community adapters rather than embedding account passwords or scraping private endpoints.

GameVault is not affiliated with Valve, Microsoft, Sony, Discord or Microsoft Power BI.
