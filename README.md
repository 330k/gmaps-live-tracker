# gmaps-live-tracker

Export a user's **Google Maps live location share** to CSV.

Given a public Google Maps location-sharing link, this tool fetches the shared
person's **timestamp, latitude, longitude, accuracy, address, and name** and
records them to a CSV file. It can take a single snapshot or poll continuously
to build a track log.

> Works only with links that the person has **publicly shared** via Google Maps'
> "Share your location" feature. No Google account or API key is required.

## Features

- Accepts a share link directly (`https://maps.app.goo.gl/...` or a full `https://www.google.com/maps/...` URL)
- Single-shot (`--once`) or continuous polling mode
- Appends to CSV, de-duplicating by measurement timestamp
- No third-party dependencies — Python 3 standard library only

## Requirements

- Python 3.8+

## Installation

```bash
git clone https://github.com/<your-account>/gmaps-live-tracker.git
cd gmaps-live-tracker
```

No dependencies to install.

## Usage

```bash
# Take a single snapshot
python3 gmaps_live_tracker.py "https://maps.app.goo.gl/XXXX" --once

# Poll every 15 seconds and append to track.csv (Ctrl+C to stop)
python3 gmaps_live_tracker.py "https://maps.app.goo.gl/XXXX" -o track.csv -i 15
```

### Options

| Option             | Description                                              | Default     |
|--------------------|----------------------------------------------------------|-------------|
| `url`              | Google Maps location-sharing link (positional, required) | —           |
| `-o`, `--output`   | Output CSV path                                          | `track.csv` |
| `-i`, `--interval` | Polling interval in seconds                              | `15`        |
| `--once`           | Fetch once and exit                                      | off         |

## Output columns

| Column                   | Description                                                           |
|--------------------------|-----------------------------------------------------------------------|
| `timestamp_local`        | Measurement time on the sharer's device (sharer's timezone, ISO 8601) |
| `timestamp_unix_ms`      | Same instant as Unix epoch milliseconds (stable unique key)           |
| `latitude` / `longitude` | Coordinates (WGS84)                                                   |
| `accuracy_m`             | Reported accuracy radius in meters                                    |
| `address`                | Reverse-geocoded address from Google                                  |
| `name`                   | Sharer's display name                                                 |
| `user_id`                | Sharer's account ID                                                   |
| `fetched_at`             | Time the row was fetched (collector's clock)                          |

## Notes

- Google updates the shared location roughly every 30–60 seconds. Polling more frequently returns the same value, so rows are de-duplicated by `timestamp_unix_ms`.
- When sharing is stopped or expires, no location is returned; empty results are not written.
- Points with a large `accuracy_m` are less reliable — treat them accordingly.

## Legal & privacy

Use this tool only with the sharer's consent and within the limits of applicable
laws and Google's Terms of Service. You are responsible for how you collect and
use location data.

## License

MIT