# 🎬 cinema-jatara — CinemaJatara Platform

A Telugu cinema news portal with an integrated creator economy (JataraConnect) and an AI-powered daily content pipeline.

> **Tagline:** తెలుగు సినిమా వేదిక — news, exclusive interviews, and direct fan-to-star monetisation.

---

## What's in this repo

| Part | What it is | Stack |
|------|-----------|-------|
| **Frontend** | News portal, admin panel, JataraConnect (subscriptions), JataraVault (VOD royalties), strategy dashboard | Next.js / React |
| **Backend** | Razorpay payments, subscriptions, creator payouts, webhooks, admin APIs | FastAPI (Python) |
| **Scraper** | Daily article automation from 8 Telugu RSS feeds + Claude AI enhancement | Python |
| **Database** | Full Postgres schema | Supabase |
| **CI** | Auto-runs the scraper every 6 hours | GitHub Actions |

---

## Repository structure

```
jatara/
├── frontend/                           # Next.js 14 (App Router) — the live site
│   ├── app/
│   │   ├── layout.js                   # Root layout + fonts
│   │   ├── globals.css
│   │   ├── page.js                     # Home (server component, reads Supabase, ISR 5min)
│   │   ├── article/[id]/page.js        # Article detail
│   │   └── category/[slug]/page.js     # Category listing
│   ├── components/
│   │   ├── Header.js
│   │   ├── BreakingTicker.js           # client component
│   │   └── ArticleCards.js
│   ├── lib/
│   │   └── data.js                     # Supabase client + queries (mock fallback)
│   ├── package.json
│   ├── next.config.mjs
│   ├── .env.local.example              # copy to .env.local, add Supabase keys
│   └── _reference_mockups/             # original standalone UI mockups (not built)
│       ├── NewsPortal.jsx              #   - design reference for the live pages
│       ├── AdminPanel.jsx              #   - to be wired up in a later phase
│       ├── JataraConnect.jsx           #   - creator subscriptions (phase 2)
│       ├── JataraVault.jsx             #   - VOD royalties (phase 2)
│       ├── StrategyDashboard.jsx
│       └── useRazorpay.js
│
├── backend/
│   ├── app/
│   │   └── main.py                     # FastAPI: payments, subscriptions, payouts
│   ├── scraper/
│   │   └── scraper.py                  # Daily article scraper + AI enhancement
│   ├── requirements.txt
│   └── Procfile                        # Railway deploy config
│
├── database/
│   └── schema.sql                      # Full Supabase schema (run this first)
│
├── docs/
│   ├── GO_LIVE_GUIDE.md                # Step-by-step launch playbook
│   ├── DAILY_ARTICLES_SETUP.md         # Scraper automation setup
│   └── PROJECT_SUMMARY.md              # High-level overview & economics
│
├── .github/workflows/
│   └── daily-articles.yml              # Scheduled scraper (every 6h)
│
├── .env.template                       # Copy to .env and fill in
├── .gitignore
└── README.md                           # You are here
```

---

## Quick start

### 1. Database (5 min)
Run `database/schema.sql` in the Supabase SQL editor.

### 2. Backend (10 min)
```bash
cd backend
pip install -r requirements.txt
cp ../.env.template .env   # fill in your keys
uvicorn app.main:app --reload
```

### 3. Frontend (10 min)
The frontend is a real Next.js 14 app. To run it:
```bash
cd frontend
cp .env.local.example .env.local   # add your Supabase URL + anon key
npm install
npm run dev                        # http://localhost:3000
```
Without the env vars it runs in **demo mode** with sample articles. With them, the home page,
article pages, and category pages read live from your `articles` table.

To deploy: push to GitHub, import the repo in Vercel, set the **Root Directory** to `frontend`,
add the two `NEXT_PUBLIC_SUPABASE_*` env vars, and deploy.

### 4. Scraper (5 min)
Add `SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY` as GitHub repo secrets. The workflow in `.github/workflows/daily-articles.yml` then runs automatically every 6 hours.

Full instructions: see [`docs/GO_LIVE_GUIDE.md`](docs/GO_LIVE_GUIDE.md).

---

## Economics at a glance

- **Razorpay fee:** ~2.36% per transaction (2% + 18% GST on the fee)
- **Split of net:** 40% platform / 60% creator
- **Creator payouts:** automatic via Razorpay Route

See [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md) for projections.

---

## Status

🚧 Pre-launch. Frontend UIs, backend payment flows, scraper, and schema are built. Next: wire frontend to backend, deploy, and onboard first creators.

---

_Private project. Not for distribution._
