# Data source coverage

| Source | Backfill available | Ongoing data | Status |
| --- | --- | --- | --- |
| Steam Web API | Owned games, lifetime minutes, profile, achievements and unlock times | Library snapshots and achievements | Implemented |
| PC process collector | Starts when installed | Starts, stops, duration, device and live presence | Implemented |
| Playnite export | Library, platform, playtime and last played | Periodic export/import | Planned |
| Xbox | Export or supported API where available | Playtime/achievement sync depends on account/API access | Planned adapter |
| PlayStation | Trophy exports or supported provider data | Official personal playtime API is limited | Planned import |
| RetroAchievements | Game and achievement history | API sync | Planned |
| Discord Rich Presence | Little reliable historical backfill | Current activity enrichment | Planned optional adapter |

## What Steam cannot recover

Steam returns a lifetime total and, sometimes, a rolling two-week total. It does not return the timestamp and duration of every historical play session. The first GameVault sync therefore establishes a lifetime baseline. Achievement unlock timestamps can reconstruct some historical activity but must not be treated as complete session history.

## Data provenance

Every game, session, achievement, sync and snapshot records its provider or source. Keep source labels visible when combining imports so a provider total is not mistaken for collector-observed time. The `Data health` report page identifies stale live sessions and unmatched executable names that would otherwise create gaps.
