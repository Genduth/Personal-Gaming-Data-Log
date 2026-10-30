# Power BI setup and live refresh

## Open the project

1. Start PostgreSQL and the API with `docker compose up -d`.
2. Open `powerbi/GameVault.pbip` in a current Power BI Desktop release with Power BI Project (`.pbip`) and TMDL enabled.
3. In **Transform data → Edit parameters**, set:
   - `DatabaseHost`: `localhost:5432`, or the reachable database host and port
   - `DatabaseName`: `gamevault`
4. Authenticate with PostgreSQL. For a permanent deployment, create a read-only login and grant it `USAGE` on the `powerbi` schema plus `SELECT` on its views.
5. Confirm every table uses DirectQuery storage mode.

The report source is text-based and Git-friendly. Power BI Desktop may update schema-version metadata when it first opens the project; review and commit those normal format upgrades separately from metric changes.

## How live the dashboard can be

The collector writes a heartbeat every 60 seconds. The `powerbi.live_activity` view calculates the current game and elapsed session time at query time.

- **Power BI Desktop:** use page refresh while developing, or press Refresh to see the latest heartbeat.
- **Power BI Service on shared/Pro capacity:** PostgreSQL DirectQuery works through an on-premises data gateway, but automatic page refresh is limited by the shared-capacity minimum interval.
- **Power BI Premium or Fabric capacity:** configure automatic page refresh on the Overview page at an interval supported by the capacity. This is the simplest seconds-level option for this project.
- **Fabric Real-Time Intelligence:** for high-frequency telemetry, mirror collector events into an Eventstream and Eventhouse/KQL database, then connect Power BI using DirectQuery. Keep PostgreSQL as the durable personal archive.

Microsoft disabled creation of new legacy Power BI real-time streaming semantic models in October 2024. GameVault deliberately uses DirectQuery and the current Fabric path rather than the retiring push/streaming-dataset feature.

## Recommended page refresh

| Page | Suggested cadence | Reason |
| --- | ---: | --- |
| Overview | 30–60 seconds on capacity | Shows current game and running duration |
| Sessions & habits | On interaction | Aggregates completed history |
| Achievements | After provider sync | Provider data changes only on sync |
| Data health | 1–5 minutes | Surfaces stale collector sessions and failed syncs |

## Gateway notes

Install the Microsoft on-premises data gateway on a machine that can reach PostgreSQL. Configure a PostgreSQL data source with the same server/database names used by the semantic model, map it to the published model, and test the connection. TLS is recommended even on a private network.

Do not publish database or collector credentials into the PBIP files. Power BI stores credentials in Desktop user settings or the Service/gateway connection, outside this repository.

## Suggested interactions

The included model supports:

- Date, platform, provider, game and device slicers
- Cross-filtering between the activity line, game ranking and recent sessions
- Drill-through from a game into sessions and achievements
- Conditional formatting on the weekday/hour matrix to create a gaming heatmap
- Tooltips showing session count, tracked hours and average session length

The report ships with native visuals so it has no marketplace-visual dependency.
