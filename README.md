# Career Match

Career Match is a Streamlit application for resume matching, interview preparation, and evidence-backed career guidance.

## Current version

- App version: `v0.4.0-quality`
- Product name: `Career Match`

## Core product

The app:

- uploads and extracts resume text from PDF, DOCX, or TXT
- fetches a job description from a job posting URL with graceful manual fallback
- compares resume content against the job description
- scores direct fit, transferable fit, overall fit, and interview potential
- generates resume match analysis, resume optimization, interview preparation, outreach content, and career guidance
- preserves evidence-backed recommendations with Trust Score and Evidence validation
- exports results to DOCX and PDF
- stores local application history in SQLite

## Primary tagline

Match your resume to any job and understand exactly where you stand.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set required environment variables:

```bash
export OPENAI_API_KEY="your_real_key_here"
```

Optional:

```bash
export OPENAI_MODEL="gpt-4.1-mini"
export APP_ENV="development"
export APP_LOG_LEVEL="INFO"
export SENTRY_DSN=""
export SENTRY_ENVIRONMENT="development"
export SENTRY_TRACES_SAMPLE_RATE="0.1"
```

4. Run the app:

```bash
streamlit run app.py
```

If `OPENAI_API_KEY` is missing, empty, or still set to `your_api_key_here`, the app automatically runs in Demo Mode so the full flow can still be tested.

## Clean restart

If changes do not appear in the browser, an older Streamlit process may still be serving a stale port.

1. Stop the current Streamlit process with `Ctrl+C`.
2. Check active local ports:

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep 850
```

3. If needed, stop the old process:

```bash
pkill -f "streamlit run app.py"
```

4. Start the app again:

```bash
streamlit run app.py
```

5. Use the newest URL printed in the terminal.

## Production deployment package

This repo includes a production deployment scaffold for Render using Docker:

- `Dockerfile`
- `render.yaml`
- `deploy/Caddyfile`
- `deploy/supervisord.conf`
- `.streamlit/config.toml`
- `static/manifest.webmanifest`
- `static/sw.js`
- `static/offline.html`
- PWA icons in `static/`

### Production architecture

- Public web traffic terminates at `Caddy`
- `Caddy` serves PWA assets directly:
  - `manifest.webmanifest`
  - `sw.js`
  - install icons
  - offline page
- `Caddy` reverse proxies the application to Streamlit on `127.0.0.1:8501`
- Streamlit runs the existing app unchanged behind the proxy
- Logging is written to stdout and rotating local log files in `logs/`
- Optional monitoring is enabled through `SENTRY_DSN`

### Recommended hosting platform

- Platform: `Render`
- Service type: `Docker web service`
- Plan: `Free`
- Default database mode: `SQLite`
- Reason: straightforward Python deployment, HTTPS by default, and support for a reverse-proxy front end for PWA assets without requiring a separate database service

## Production environment variables

Required:

- `OPENAI_API_KEY`

Recommended:

- `DATABASE_URL` only if you want to override SQLite and use PostgreSQL
- `OPENAI_MODEL`
- `APP_ENV=production`
- `APP_LOG_LEVEL=INFO`
- `SENTRY_DSN`
- `SENTRY_ENVIRONMENT=production`
- `SENTRY_TRACES_SAMPLE_RATE=0.1`
- `STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true`
- `STREAMLIT_BROWSER_GATHER_USAGE_STATS=false`

## PWA behavior

The app includes:

- `manifest.webmanifest`
- install icons for mobile and desktop
- service worker registration
- offline fallback page

### Installation

iPhone:

1. Open the deployed site in Safari.
2. Tap the Share button.
3. Choose `Add to Home Screen`.

Android:

1. Open the deployed site in Chrome.
2. Tap the install prompt or browser menu.
3. Choose `Install app` or `Add to Home Screen`.

Desktop:

1. Open the deployed site in Chrome or Edge.
2. Click the install icon in the address bar.
3. Confirm installation.

Note:

- Career Match remains a networked Streamlit app, so installation support is included, but full offline analysis is intentionally limited.

## Monitoring and operational readiness

The deployment package includes:

- structured application logging
- rotating file logs in `logs/app.log`
- stdout logs for container platforms
- optional Sentry exception monitoring
- production static asset routing for PWA files
- graceful error handling around major application flows

## Validation checklist

Use these checks after deployment:

1. Open the production URL on desktop, tablet, and mobile widths.
2. Confirm the landing page loads first.
3. Click `Start Free Analysis`.
4. Verify resume upload works.
5. Verify job URL extraction works.
6. Verify manual fallback works when extraction is blocked.
7. Verify OpenAI generation works with a real API key.
8. Verify DOCX and PDF exports download successfully.
9. Verify the app is installable as a PWA.
10. Verify logs appear in the hosting platform console and Sentry receives test exceptions if configured.

## Hosting cost estimate

Typical monthly estimate for Render:

- Free web service: `$0/month`
- Sentry free tier: `$0` to start
- OpenAI API: usage-based and separate from hosting

## Guardrails

- The app does not intentionally fabricate experience.
- It should not add unsupported tools, platforms, certifications, or technologies.
- Outputs are designed to stay concise, professional, and ATS-friendly.
- Review all generated content before using it in a real application.

## Local data

- SQLite database file: `database/applications.db`
- Log directory: `logs/`

## Database behavior

- SQLite is the default database engine whenever `DATABASE_URL` is not set.
- PostgreSQL remains supported if `DATABASE_URL` is provided with a `postgres://` or `postgresql://` value.
- The database schema initializes automatically at startup through `init_db()`.
- On Render Free, SQLite uses local container file storage. This keeps the app self-contained, but local data is not durable across full redeploys or instance replacement.

## Diagnostics

The visible UI keeps diagnostics hidden behind the `Diagnostics` expander. It exposes:

- app version
- build timestamp
- local URL
- process ID
