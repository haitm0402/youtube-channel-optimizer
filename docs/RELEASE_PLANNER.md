# Release Planner

Release Planner is the operations calendar for many YouTube music channels. It is
local-first and requires no YouTube API, Google Calendar, AI API, or browser automation.

Launch the existing app:

```powershell
py -3 app.py --gui
```

Open **RELEASE PLANNER** from the top bar.

## Channel schedules

Each planner channel stores:

- channel name and target market
- IANA timezone, for example `Asia/Ho_Chi_Minh` or `America/New_York`
- default upload time in 24-hour `HH:MM`
- preferred weekdays
- notes

**USE NEXT AVAILABLE SLOT** selects the next preferred weekday/default time that is
not already occupied by another active release on that same channel.

## Releases

Each release stores its channel, song title, optional video title, publish date/time,
timezone, workflow status, notes, optional YouTube URL, and readiness for:

- Audio
- Thumbnail
- Video
- SEO

The table shows the original publish time and automatically converts it to Vietnam
time (`Asia/Ho_Chi_Minh`) for operations.

Statuses:

`PLANNED`, `IN_PROGRESS`, `READY`, `SCHEDULED`, `PUBLISHED`, `HOLD`.

The dashboard summarizes Today, Next 7 Days, Missing Assets, Ready and Scheduled.
Filters support Today, Next 7 Days, Next 30 Days, All, channel and status.

Export creates an Excel-friendly UTF-8 CSV under:

```text
exports/release_planner/
```

Runtime data is saved atomically in:

```text
data/release_planner.json
```

The first version does not publish to YouTube or create calendar events. Those can be
added later after the local planning workflow is proven useful.
