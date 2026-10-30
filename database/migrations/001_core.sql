CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS gaming;

CREATE TABLE IF NOT EXISTS gaming.schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE gaming.accounts (
  account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  external_id text NOT NULL,
  display_name text,
  profile_url text,
  avatar_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_synced_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, external_id)
);

CREATE TABLE gaming.games (
  game_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  slug text NOT NULL,
  primary_platform text NOT NULL,
  provider text NOT NULL,
  external_id text NOT NULL,
  cover_url text,
  lifetime_playtime_minutes integer NOT NULL DEFAULT 0 CHECK (lifetime_playtime_minutes >= 0),
  last_played_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, external_id)
);

CREATE INDEX games_last_played_idx ON gaming.games (last_played_at DESC NULLS LAST);

CREATE TABLE gaming.devices (
  device_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_name text NOT NULL UNIQUE,
  platform text,
  collector_version text,
  last_seen_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE gaming.game_aliases (
  alias_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  game_id uuid NOT NULL REFERENCES gaming.games(game_id) ON DELETE CASCADE,
  executable text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX game_aliases_executable_idx ON gaming.game_aliases (lower(executable));

CREATE TABLE gaming.game_sessions (
  session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  game_id uuid NOT NULL REFERENCES gaming.games(game_id) ON DELETE CASCADE,
  device_id uuid REFERENCES gaming.devices(device_id) ON DELETE SET NULL,
  source text NOT NULL,
  executable text,
  started_at timestamptz NOT NULL,
  ended_at timestamptz,
  last_heartbeat_at timestamptz,
  duration_seconds integer GENERATED ALWAYS AS (
    CASE
      WHEN ended_at IS NULL THEN NULL
      ELSE greatest(0, extract(epoch FROM (ended_at - started_at))::integer)
    END
  ) STORED,
  status text NOT NULL CHECK (status IN ('active', 'closed', 'abandoned')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE UNIQUE INDEX one_active_game_per_device_idx
  ON gaming.game_sessions (game_id, device_id) WHERE status = 'active';
CREATE INDEX game_sessions_started_idx ON gaming.game_sessions (started_at DESC);
CREATE INDEX game_sessions_live_idx ON gaming.game_sessions (status, last_heartbeat_at DESC);

CREATE TABLE gaming.collector_events (
  event_id uuid PRIMARY KEY,
  event_type text NOT NULL CHECK (event_type IN ('start', 'heartbeat', 'stop')),
  device_id uuid NOT NULL REFERENCES gaming.devices(device_id) ON DELETE CASCADE,
  executable text NOT NULL,
  occurred_at timestamptz NOT NULL,
  session_id uuid REFERENCES gaming.game_sessions(session_id) ON DELETE SET NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE gaming.unmatched_processes (
  executable text PRIMARY KEY,
  device_id uuid REFERENCES gaming.devices(device_id) ON DELETE SET NULL,
  first_seen_at timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL,
  seen_count integer NOT NULL DEFAULT 1
);

CREATE TABLE gaming.achievements (
  achievement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  game_id uuid NOT NULL REFERENCES gaming.games(game_id) ON DELETE CASCADE,
  provider text NOT NULL,
  external_id text NOT NULL,
  name text NOT NULL,
  description text,
  icon_url text,
  is_unlocked boolean NOT NULL DEFAULT false,
  unlocked_at timestamptz,
  is_hidden boolean NOT NULL DEFAULT false,
  rarity_percent numeric(6,3),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (game_id, provider, external_id),
  CHECK (rarity_percent IS NULL OR rarity_percent BETWEEN 0 AND 100)
);

CREATE INDEX achievements_unlocked_idx
  ON gaming.achievements (is_unlocked, unlocked_at DESC NULLS LAST);

CREATE TABLE gaming.playtime_snapshots (
  game_id uuid NOT NULL REFERENCES gaming.games(game_id) ON DELETE CASCADE,
  account_id uuid REFERENCES gaming.accounts(account_id) ON DELETE SET NULL,
  captured_at timestamptz NOT NULL,
  lifetime_playtime_minutes integer NOT NULL CHECK (lifetime_playtime_minutes >= 0),
  recent_playtime_minutes integer,
  provider text NOT NULL,
  PRIMARY KEY (game_id, captured_at)
);

CREATE TABLE gaming.sync_runs (
  sync_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  status text NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  records_processed integer NOT NULL DEFAULT 0,
  warning_count integer NOT NULL DEFAULT 0,
  error_message text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX sync_runs_provider_idx ON gaming.sync_runs (provider, started_at DESC);
