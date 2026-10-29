# Codebase Physical Structure

**Analysis Date:** 2026-10-24

## Directory Layout

```
Code Guardian AI/
├── .planning/                  # GSD Project planning, state, roadmap, codebase maps
│   ├── codebase/               # 7 Codebase intelligence maps (Stack, Arch, Struct, etc.)
│   ├── config.json             # GSD workflow and engine configuration
│   ├── PROJECT.md              # Project mission and specification
│   ├── ROADMAP.md              # Milestone and phase roadmap
│   └── STATE.md                # Real-time execution and progress state
├── apps/
│   ├── backend/                # Python FastAPI, LangGraph, Scanners, RAG, Workers
│   │   ├── app/
│   │   │   ├── agents/         # LangGraph multi-agent graph & 5 specialist agents
│   │   │   ├── api/v1/         # Versioned REST endpoints (auth, repos, reviews, findings)
│   │   │   ├── database/       # Async database engine, session factory, migrations
│   │   │   ├── github/         # Webhook ingress, HMAC verification, API client, check runs
│   │   │   ├── localization/   # Multilingual translations (Hindi, Hinglish, Urdu, etc.)
│   │   │   ├── metrics/        # Academic evaluation & SLA performance tracking
│   │   │   ├── models/         # 13 SQLAlchemy async relational models
│   │   │   ├── optimization/   # AST static code complexity & NLP optimization engine
│   │   │   ├── rag/            # ChromaDB vector store & policy grounding engine
│   │   │   ├── remediation/    # 5-stage sandboxed fix engine & draft PR generator
│   │   │   ├── reports/        # Sections A-M comprehensive report generator
│   │   │   ├── risk/           # Deterministic risk engine (score 0-100 & grade A-F)
│   │   │   ├── scanners/       # Bandit, Semgrep, Gitleaks, ESLint adapters
│   │   │   ├── security/       # PromptGuard (OWASP LLM01), secret masking, path checks
│   │   │   ├── voice/          # PCM WAV audio synthesis & streaming service
│   │   │   ├── workers/        # Redis Streams & In-Memory review queue workers
│   │   │   ├── config.py       # Pydantic Settings & environment variables
│   │   │   └── main.py         # FastAPI application entrypoint & middleware setup
│   │   ├── tests/              # 194 automated unit and integration tests
│   │   │   ├── integration/    # Database, webhook, E2E lifecycle, worker tests
│   │   │   ├── unit/           # Scanners, agents, RAG, risk, optimization, voice tests
│   │   │   └── conftest.py     # SQLite async fixtures and test client overrides
│   │   └── pyproject.toml      # Python dependencies and pytest configuration
│   └── frontend/               # React 18, TypeScript, Vite, Tailwind SPA
│       ├── src/
│       │   ├── components/     # UI components (ScoreGauge, DiffViewer, Header, Sidebar)
│       │   ├── pages/          # 11 Application views (Dashboard, PRs, Findings, Voice)
│       │   ├── services/       # Typed API client (`api.ts`) and data interfaces
│       │   ├── App.tsx         # Root application router and route transitions
│       │   ├── main.tsx        # React DOM render entry point
│       │   └── index.css       # Tailwind CSS & Cosmic Plasma Nebula styling tokens
│       ├── package.json        # Frontend dependencies & npm scripts
│       ├── tsconfig.json       # TypeScript compiler options
│       └── vite.config.ts      # Vite dev server and build rollup settings
├── datasets/                   # Sample benchmark repositories and test fixtures
├── docs/                       # Comprehensive architectural & design documentation (18 files)
├── policies/                   # Default markdown security and engineering policies
├── docker-compose.yml          # Local multi-service development compose file
├── docker-compose.prod.yml     # Production hardened multi-container deployment
├── .env.example                # Development environment variable template
├── .env.production.example     # Production environment variable template
└── README.md                   # Getting started and setup guide
```

## Key File Locations & Entry Points

- **Backend Application Entry:** [`apps/backend/app/main.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/main.py)
- **Frontend Entry:** [`apps/frontend/src/main.tsx`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/frontend/src/main.tsx)
- **LangGraph Multi-Agent Graph:** [`apps/backend/app/agents/graph.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/agents/graph.py)
- **Deterministic Risk Engine:** [`apps/backend/app/risk/engine.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/risk/engine.py)
- **GitHub Webhook Ingress:** [`apps/backend/app/github/webhook.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/github/webhook.py)
- **Test Suite Entry:** [`apps/backend/tests/conftest.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/tests/conftest.py)

---
*Structure analysis: 2026-10-24*
