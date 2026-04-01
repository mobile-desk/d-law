# The Law (d law)

Django app: guided legal intake chat, cases, and professional matching.

## Netlify

**Netlify is not a fit for this project.** It hosts static sites and short-lived serverless functions. A Django app needs a long-running Python process, a database, sessions, and file uploads—use a **Python / Postgres** host instead.

**Good options:** [Render](https://render.com) (free tier), [Railway](https://railway.app), [Fly.io](https://fly.io), [PythonAnywhere](https://www.pythonanywhere.com).

This repo includes **Render** configuration so you can deploy with Postgres, Gunicorn, and HTTPS in a few minutes.

## Deploy on Render

1. Push the repo to GitHub (or GitLab / Bitbucket).
2. In Render: **New → Blueprint** → connect the repo and select `render.yaml`.
3. After the first deploy, open the web service → **Environment** and set:
   - **`DJANGO_ALLOWED_HOSTS`** — your service hostname, e.g. `legal-access.onrender.com` (no `https://`).
   - **`DJANGO_CSRF_TRUSTED_ORIGINS`** — full origin, e.g. `https://legal-access.onrender.com` (comma-separated if several).
4. **Redeploy** the web service so Django picks up the new env vars.
5. Optional: add **`GROQ_API_KEY`** (and model vars from `.env.example`) for AI replies.

Build runs `collectstatic`, `migrate`, and `populate_lawyer_profiles --bootstrap 8` (seeds eight demo lawyers **only** when the database has no lawyer users yet, so redeploys do not duplicate them).

The free web instance may spin down when idle; upgrade if you need always-on.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edit secrets
python manage.py migrate
python manage.py runserver
```

Without `DATABASE_URL`, the app uses **SQLite** (`db.sqlite3`).

## Environment variables

See `.env.example`. Production needs a strong `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DATABASE_URL` (Render wires this from the managed Postgres).
