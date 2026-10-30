CREATE SCHEMA IF NOT EXISTS powerbi;

CREATE OR REPLACE VIEW powerbi.games AS
SELECT
  game_id,
  title,
  slug,
  primary_platform AS platform,
  provider,
  external_id,
  cover_url,
  lifetime_playtime_minutes,
  last_played_at,
  created_at,
  updated_at
FROM gaming.games;

CREATE OR REPLACE VIEW powerbi.sessions AS
SELECT
  s.session_id,
  s.game_id,
  s.device_id,
  d.device_name,
  s.source,
  s.executable,
  s.started_at,
  s.started_at::date AS session_date,
  extract(hour FROM s.started_at)::integer AS start_hour,
  extract(isodow FROM s.started_at)::integer AS weekday_number,
  s.ended_at,
  coalesce(
    s.duration_seconds,
    greatest(0, extract(epoch FROM (now() - s.started_at))::integer)
  ) AS duration_seconds,
  s.status,
  s.last_heartbeat_at,
  (s.status = 'active' AND s.last_heartbeat_at > now() - interval '2 minutes') AS is_live
FROM gaming.game_sessions s
LEFT JOIN gaming.devices d ON d.device_id = s.device_id;

CREATE OR REPLACE VIEW powerbi.live_activity AS
SELECT
  s.session_id,
  s.game_id,
  g.title,
  g.cover_url,
  d.device_name,
  s.executable,
  s.started_at,
  s.last_heartbeat_at,
  greatest(0, extract(epoch FROM (now() - s.started_at))::integer) AS live_duration_seconds,
  CASE
    WHEN s.last_heartbeat_at > now() - interval '2 minutes' THEN 'Playing now'
    ELSE 'Collector stale'
  END AS presence_status
FROM gaming.game_sessions s
JOIN gaming.games g ON g.game_id = s.game_id
LEFT JOIN gaming.devices d ON d.device_id = s.device_id
WHERE s.status = 'active';

CREATE OR REPLACE VIEW powerbi.achievements AS
SELECT
  achievement_id,
  game_id,
  provider,
  external_id,
  name,
  description,
  icon_url,
  is_unlocked,
  unlocked_at,
  unlocked_at::date AS unlocked_date,
  is_hidden,
  rarity_percent,
  updated_at
FROM gaming.achievements;

CREATE OR REPLACE VIEW powerbi.playtime_snapshots AS
SELECT
  game_id,
  account_id,
  captured_at,
  captured_at::date AS captured_date,
  lifetime_playtime_minutes,
  recent_playtime_minutes,
  provider,
  lifetime_playtime_minutes - lag(lifetime_playtime_minutes) OVER (
    PARTITION BY game_id ORDER BY captured_at
  ) AS minutes_since_previous_snapshot
FROM gaming.playtime_snapshots;

CREATE OR REPLACE VIEW powerbi.sync_status AS
SELECT
  sync_run_id,
  provider,
  status,
  started_at,
  finished_at,
  records_processed,
  warning_count,
  error_message,
  extract(epoch FROM (coalesce(finished_at, now()) - started_at))::integer AS duration_seconds
FROM gaming.sync_runs;

CREATE OR REPLACE VIEW powerbi.data_quality AS
SELECT 'Unmatched executables'::text AS check_name,
       count(*)::bigint AS issue_count,
       max(last_seen_at) AS last_observed_at
FROM gaming.unmatched_processes
UNION ALL
SELECT 'Stale active sessions', count(*)::bigint, max(last_heartbeat_at)
FROM gaming.game_sessions
WHERE status = 'active' AND last_heartbeat_at < now() - interval '2 minutes'
UNION ALL
SELECT 'Games without cover art', count(*)::bigint, max(updated_at)
FROM gaming.games
WHERE cover_url IS NULL;

CREATE OR REPLACE VIEW powerbi.date_dimension AS
SELECT
  day::date AS date,
  extract(year FROM day)::integer AS year,
  extract(quarter FROM day)::integer AS quarter,
  extract(month FROM day)::integer AS month_number,
  to_char(day, 'Month') AS month_name,
  to_char(day, 'Mon YYYY') AS month_year,
  extract(isodow FROM day)::integer AS weekday_number,
  to_char(day, 'Day') AS weekday_name,
  extract(week FROM day)::integer AS iso_week,
  (extract(isodow FROM day) IN (6, 7)) AS is_weekend
FROM generate_series(date '2010-01-01', current_date + interval '1 year', interval '1 day') AS day;

CREATE OR REPLACE VIEW powerbi.activity_heatmap AS
SELECT
  extract(isodow FROM started_at)::integer AS weekday_number,
  trim(to_char(started_at, 'Day')) AS weekday_name,
  extract(hour FROM started_at)::integer AS start_hour,
  count(*)::bigint AS session_count,
  sum(coalesce(duration_seconds, extract(epoch FROM (now() - started_at))::integer))::bigint
    AS duration_seconds
FROM gaming.game_sessions
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW powerbi.metrics AS
SELECT 1::integer AS metric_key;
