# Architecture

## Design goals

GameVault keeps raw operational data separate from the Power BI contract. Collectors and provider adapters write to the `gaming` schema; Power BI receives stable, read-only views from the `powerbi` schema. That boundary lets ingestion evolve without breaking report field names.

PostgreSQL is the source of truth. It is a better fit than a local file database because Power BI supports PostgreSQL DirectQuery, the API and collector can write concurrently, and an on-premises data gateway can securely expose it to Power BI Service.

## Event flow

The collector fetches a catalog of mapped executable names, intersects it with the current process list, and emits idempotent `start`, `heartbeat` and `stop` events. Each event has a UUID. The API stores that UUID before changing session state, so a queued retry cannot create duplicate playtime.

A live session remains visible while its most recent heartbeat is less than two minutes old. A stopped session stores an end timestamp and a generated duration. Stale sessions stay visible in the data-health page instead of being silently guessed or deleted.

## Historical data

Steam's owned-games endpoint supplies the current lifetime total for each game. GameVault stores both the latest total and an immutable timestamped snapshot. The first snapshot is a baseline; later snapshots show accumulated playtime between syncs. Steam achievement unlock timestamps provide genuine historical events where the user profile exposes them.

The collector supplies accurate session history only from installation onward. Imported records retain their source so Power BI can distinguish observed sessions, provider totals and user-supplied history.

## Security boundaries

- The collector and mutation endpoints use a shared bearer token.
- The Steam API key exists only in the API environment.
- Power BI should use a read-only PostgreSQL login restricted to the `powerbi` schema.
- No gaming-account password is collected.
- The API does not expose a public browsing endpoint for personal history.

For an Internet-hosted deployment, put the API behind TLS and an identity-aware reverse proxy. Do not expose PostgreSQL directly to the public Internet.
