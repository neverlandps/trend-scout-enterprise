# Trend Scout Enterprise

AI-powered trend scouting automation for enterprise business teams.

## Overview

Trend Scout Enterprise is a self-service, multi-user platform that automatically collects signals from curated sources (RSS, arXiv, web search, custom APIs), analyzes them with user-managed OpenAI-compatible LLMs, scores items with user-maintainable weights, and generates three ready-to-use outputs:

- **PDF Reports** (priority in P0)
- **Zoom Community Media Cards** (P1)
- **PowerPoint Briefs** (P1)

## Architecture

```
trend-scout-enterprise/
├── backend/          # FastAPI + Python services
│   ├── src/trend_scout_enterprise/
│   └── tests/
├── frontend/         # React + TypeScript SPA
│   └── src/
├── docs/             # Architecture, API specs
└── deployment/       # Docker, Azure, SPFx
```

## Quick Start

```bash
cd /home/ps/trend-scout-enterprise
# Backend
python -m venv venv
source venv/bin/activate
pip install -e backend/
cd backend
uvicorn trend_scout_enterprise.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Project Status

- P0 (MVP): in planning
- Workspace initialized: `/home/ps/trend-scout-enterprise/`
- Planning artifacts: `/home/ps/team-vault/projects/trend-scout-enterprise/planning/`

## License

Proprietary — internal enterprise use.
