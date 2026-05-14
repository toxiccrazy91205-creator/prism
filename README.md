<p align="center">
  <img src="assets/banner.png" alt="Prism — See your product from every angle" width="100%" />
</p>

<p align="center">
  <strong>Product intelligence platform for product teams</strong>
  <br />
  <em>Track competitors, research your industry, map UX flows, run UAT — all in one place</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-10b981?style=flat-square" alt="Version" />
  <img src="https://img.shields.io/badge/AI-NVIDIA_NIM-76B900?style=flat-square&logo=nvidia&logoColor=white" alt="AI Provider" />
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Next.js-14-000000?style=flat-square&logo=next.js" alt="Next.js" />
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" />
</p>

---

Prism is a product operating system for PMs. It has been migrated to **NVIDIA NIM APIs** for high-performance, cost-effective inference. It combines automated UAT testing with autonomous competitive intelligence agents that research your market while you sleep.

---

## What It Does

- **Autonomous competitive intelligence** — AI agents discover competitors, research their features, pricing, recent launches, and strategic moves. Each finding is evidence-backed with source URLs.
- **Industry research** — Tracks industry trends, regulatory changes, market data from analyst publications.
- **UX flow mapping** — Navigates Android apps via vision-guided automation, maps every screen and flow, compares UX patterns across competitors.
- **Natural language queries** — Ask questions and get synthesized answers drawing from all agent knowledge.
- **Vision-guided UAT** — Drop in an APK, point at your Figma file, get a per-frame comparison report.
- **NVIDIA Powered** — Uses Llama 3.1 405B for reasoning and Llama 3.2 11B Vision for UX navigation.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      PM INTERFACES                             │
│  Web Dashboard (Prism)  ·  Telegram Bot  ·  Query Engine       │
└──────────────┬─────────────────────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────────┐
│               AGENT ORCHESTRATOR                               │
│  Schedules sessions · Device lock · Token budget               │
└──┬───────────────┬───────────────┬───────────────┬─────────────┘
   │               │               │               │
┌──▼────────┐ ┌───▼────────┐ ┌───▼──────────┐ ┌──▼───────────┐
│Competitive│ │ Industry   │ │ UX           │ │ UAT Runner   │
│Intel Agent│ │ Research   │ │ Intelligence │ │ (Figma+APK)  │
└──┬────────┘ └───┬────────┘ └───┬──────────┘ └──┬───────────┘
   │               │               │               │
┌──▼───────────────▼───────────────▼───────────────▼─────────────┐
│                 NVIDIA NIM AI INFRASTRUCTURE                   │
│   Llama 3.1 405B (Reasoning) · Llama 3.2 11B (Vision)          │
│   nv-embedqa-e5-v5 (Embeddings)                                │
└─────────────────────────────────────────────┬──────────────────┘
                                              │
┌─────────────────────────────────────────────▼──────────────────┐
│                SHARED KNOWLEDGE LAYER                           │
│  Entities · Relations · Observations · Artifacts · Screenshots │
│  Neon Postgres · 17 tables · NVIDIA Semantic Search            │
└────────────────────────────────────────────────────────────────┘
```

---

## Setup

### 1. Local Development (Native)

```bash
# Clone and install
git clone https://github.com/yash7agarwal/prism.git
cd prism
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: NVIDIA_API_KEY (required), DATABASE_URL (optional for local SQLite)

# Run backend
python3 -m uvicorn webapp.api.main:app --reload --port 8000

# Run frontend (separate terminal)
cd webapp/web && npm install && npm run dev
```

### 2. Local Development (Docker)

```bash
# Build and run with Docker
docker build -t prism-nvidia .
docker run -p 8000:8000 --env-file .env prism-nvidia
```

### 3. Production Deployment (Render)

1. **Connect Repository:** Create a new **Web Service** on Render and connect your GitHub repo.
2. **Runtime:** Select **Docker**.
3. **Environment Variables:**
   - `NVIDIA_API_KEY`: Your NVIDIA NIM key.
   - `DATABASE_URL`: Your Neon Postgres connection string.
   - `TAVILY_API_KEY`: Your Tavily search key.
   - `SERVICE_TYPE`: Set to `api` (or `both` if you want the bot in the same container).
4. **Deploy:** Render will build the optimized multi-stage image and deploy.

---

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `NVIDIA_API_KEY` | NVIDIA NIM API key | **Yes** |
| `DATABASE_URL` | PostgreSQL URL (Neon/Supabase) | For Prod |
| `TAVILY_API_KEY` | Tavily web search API | No |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | For Bot |
| `PRISM_AUTO_DAEMON` | Start research scheduler (1=yes) | For Prod |

---

## Final Project Status

The project is now:
- **Free-Tier Optimized**: Works on Render + Neon + NVIDIA Free credits.
- **Production-Ready**: Dockerized with multi-stage builds and health checks.
- **Minimal**: Zero legacy AI dependencies.
