# MatchLens

Private football analysis for one owner. Probability first, price considered separately.

## Local start

Python 3.12 or newer is required. From this folder:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
python -m app.jobs init
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open http://localhost:8000. The one-time local setup page asks for an owner password and an optional football-data.org token without displaying either. It writes a private `.env`; never upload that file or paste its contents into chat. A missing token does not enable fake fixtures. Terminal setup is also available with `python -m app.jobs setup` before starting the server.

## Data and validation

```sh
python -m app.jobs history --seasons 2022-23,2023-24,2024-25,2025-26,2026-27 --competitions PL,BL1,PD,SA,FL1
python -m app.jobs sync-results
python -m app.jobs train
python -m app.jobs ingest
python -m app.jobs predict
python -m app.jobs settle
python -m app.jobs check-coverage
```

Imports record source revisions and cache downloaded files. Training uses chronologically separate fitting, calibration and test periods. The dashboard withholds unsupported markets even if the calculation itself can produce a number. Passing historical tests does not establish future profit.

Import history once before using the dashboard's **Update recent results & validate models** button. That button then synchronizes current-season results and retrains; it does not bootstrap historical seasons into an empty database. Partial provider/history jobs return a nonzero exit code and retain a report explaining the missing data. A completed evaluation with no qualifying markets is not a job failure.

Initial safeguards: at least 300 training, 200 eligible calibration and 200 eligible test matches; calibration error at most 0.08; Brier and log loss no worse than the expanding historical-frequency baseline; at least 50 test examples in the predicted probability band. Each team also needs 10 matches in the preceding year and a result within 60 days. League results/model validation must be at most 14 days old, fixtures at most 12 hours old, and displayed estimates expire within five minutes or at kickoff. These are provisional research safeguards, not established accuracy promises. The 70% candidate cutoff and Nigeria timezone are fixed UI defaults in v0.1; timezone can be changed through `APP_TIMEZONE`.

The six market groups are total Over 1.5, total Under 4.5, home Over 0.5, away Over 0.5, double chance (1X/X2/12) and both teams to score (Yes/No). All use regulation time including stoppage time.

## Providers and scope

- Current fixtures/results: football-data.org, configured with `FOOTBALL_DATA_TOKEN`. Football data provided by the Football-Data.org API.
- Historical results: openfootball/football.json, CC0/public domain. Each import pins a Git revision; source availability is distinct from validated prediction coverage.
- Optional reference odds: The Odds API. Nigerian/SportyBet coverage is not assumed. No-value states remain visible when the configured feed lacks a matching market.

Team logos are not included. Names from different sources require explicit identity mappings. New teams and stale/conflicting data are withheld from recommendations.

## Hosting

The hosted app requires PostgreSQL, `SECURE_COOKIES=true`, a password hash, and explicit `ALLOWED_HOSTS`. SQLite is only for local use. Deploy configuration is provided but no service is provisioned automatically.

Use an available free web host and a persistent free PostgreSQL account only after verifying hard spending controls. Free hosts may sleep; the page shows data timestamps and does not depend on a continuously running web process. The supplied GitHub workflow is manual by default; scheduled operation requires deliberately enabling it after verifying quota limits. Keep secrets in the provider's secret manager.

Before enabling scheduled jobs, run `history` once against that PostgreSQL database, followed by `sync-results` and `train`. No cloud account, free-tier eligibility, public URL or billing control has been configured or verified by this local build.

Do not put the application behind an unauthenticated tunnel. Use HTTPS for access away from the local computer.

## Verification

```sh
pip install -e '.[dev]'
python -m pytest -q
```

Browser and PostgreSQL checks require their respective local services; see the release report for which checks actually ran. Test fixtures are synthetic and never substitute for real predictions. Data downloads and model fitting can take several minutes.

Run browser QA with `python tests/browser/check_ui.py` after `python -m playwright install chromium`. Set `CHROMIUM_EXECUTABLE` if using an existing Chromium binary. Set `TEST_POSTGRES_URL` to a dedicated test database to enable the PostgreSQL persistence test. Browser QA uses a separate temporary database; do not point integration tests at a production database.

## Recovery

Preserve the PostgreSQL database (or local `data/matchlens.db`), `.env` in secure storage, and the recorded model versions. Back up using the database provider's supported export; never rely on a free host's local filesystem. A failed model does not replace the last active validated model. Fixture changes invalidate old recommendations, while the ledger retains what was originally predicted.
