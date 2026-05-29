# AGENTS.md

## Project Overview

Auto_Upt is a multi-platform content creation and publishing assistant.
The planned architecture is:

- Content hub: normalize Markdown, rich text, and video metadata into a unified content IR.
- Platform adapters: render content IR into drafts for WeChat, Bilibili, Zhihu, Xiaohongshu, and future platforms.
- AI Agent orchestration: analyze content, rewrite for platform style, lint format, review compliance, simulate publishing, and later recover from publishing failures.

The current phase is a skeleton for phase one only. Do not implement real publishing, account authorization, browser auto-fill, or production automation unless explicitly requested.

## Repository Layout

```text
backend/                Python backend root
backend/app/api/        FastAPI route layer
backend/app/core/       Settings and shared infrastructure
backend/app/db/         Database sessions and persistence helpers
backend/app/models/     Domain models or ORM models
backend/app/schemas/    Pydantic request/response schemas
backend/app/services/   Business use-case orchestration
backend/app/adapters/   Platform-specific rendering, validation, simulation, publishing
backend/app/agents/     AI Agent workflow orchestration
backend/app/automation/ Playwright/browser automation helpers
backend/app/tasks/      Celery tasks and retry logic
frontend/               Vue 3 + Element Plus workspace skeleton
docs/                   Architecture, API contract, adapter design, roadmap
tests/                  Backend test skeleton
```

## Current Conventions

- Keep `__init__.py` only in Python package directories.
- Do not add `__init__.py` to `frontend/` or `docs/`.
- Use `.gitkeep` for empty non-Python directories that must be committed.
- Keep first-phase behavior simulation-only: generate previews, validation reports, task state, and screenshot placeholders.
- Keep platform rules in adapter profiles instead of hardcoding them into core services.
- Keep adapters behind a common interface with capabilities, render, validate, publish, and simulate responsibilities.
- Keep agents decoupled from concrete platform implementations; adapters should be exposed as tools when real agent integration is added.

## Platform Adapter Notes

New platforms should be added under:

```text
backend/app/adapters/<platform>/
  adapter.py
  renderer.py
  profile.yaml
```

Adapters should own platform limits, rendering rules, validation rules, simulation, and publish-mode handling. Core services should consume adapter capabilities and profiles without knowing platform internals.

## Development Commands

Install and run the MVP backend with:

```powershell
python -m pip install -r requirements.txt
docker compose up -d postgres redis
uvicorn backend.app.main:app --reload
docker compose down
```

There is not yet a frontend package manifest or configured automated test suite. Add those before introducing frontend runtime code or relying on CI-style checks.

## Editing Guidance

- Preserve the Chinese project documentation style in `README.md` and `docs/`.
- Avoid broad refactors while the repository is still a scaffold.
- When adding backend code, follow the existing layer boundaries rather than placing business logic directly in API routes.
- When adding frontend code, initialize a normal Vue 3/Vite structure and remove obsolete `.gitkeep` files from directories that receive real files.
- Update `docs/api-contract.md`, `docs/architecture.md`, or `docs/adapter-extension.md` when changing public APIs, architecture boundaries, or adapter contracts.

