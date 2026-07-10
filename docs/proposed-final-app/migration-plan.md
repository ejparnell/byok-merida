# Migration Plan

This plan moves the working prototype toward the proposed FastAPI and React app without throwing away the proven workflow.

The safest path is to preserve contracts first, then replace the runtime shell, then replace the UI surfaces.

## Phase 0: Preserve The Prototype Contract

Status: documentation phase.

Goals:

- keep current docs as the source of truth for the working prototype
- add proposed final-app docs under `docs/proposed-final-app`
- list current response contracts and workflow guardrails
- identify behavior that must not regress during the rewrite

Exit criteria:

- target architecture is documented
- target codebase structure is documented
- target workflows are documented
- migration plan is documented

## Phase 1: Contract Inventory

Goals:

- capture current result types for Capture, Analysis, and Resume Creation
- translate existing response objects into Pydantic schemas
- define OpenAPI names that match domain language
- add fixture examples for success, review, already exists, skipped, repaired, and failed results

Deliverables:

- `apps/api/merida_api/features/*/schemas.py`
- contract fixtures under `apps/api/tests/fixtures/contracts/`
- generated TypeScript API client proof of concept

Exit criteria:

- Pydantic models can represent current prototype responses
- generated TypeScript types compile in a tiny React proof

## Phase 2: FastAPI App Shell

Goals:

- create FastAPI app factory
- add settings loading and validation
- add CORS and token dependencies
- add health and readiness endpoints
- add test scaffolding with pytest

Deliverables:

- `apps/api/merida_api/app.py`
- `apps/api/merida_api/main.py`
- `apps/api/merida_api/core/settings.py`
- `apps/api/merida_api/core/auth.py`
- `apps/api/tests/test_health.py`

Exit criteria:

- `GET /api/health` works
- `GET /api/readiness` reports missing config without crashing
- protected endpoints can share one token dependency
- CI can run backend tests

## Phase 3: Workspace Adapters

Goals:

- create semantic Workspace interface
- implement Notion adapter from current Notion clients
- implement demo adapter from local fixtures
- preserve relation validation behavior

Deliverables:

- Notion workspace adapter
- demo workspace adapter
- fixture data for a safe public walkthrough
- adapter tests

Exit criteria:

- Capture, Analysis, and Resume modules can use workspace methods without knowing whether storage is Notion or demo fixtures
- demo mode can run without Notion secrets

## Phase 4: Port Job Posting Capture

Goals:

- move Capture Evidence normalization, parsing, duplicate detection, and write orchestration behind the FastAPI Job Posting Capture module
- keep extension-origin token behavior
- keep parse-only review behavior

Deliverables:

- `POST /api/job-postings/parse`
- `POST /api/job-postings/capture`
- `POST /api/job-postings/confirm`
- module and router tests

Exit criteria:

- existing capture fixtures pass against the FastAPI module
- demo adapter can create a sample Job Posting
- Notion adapter can create a real Job Posting

## Phase 5: Build React Operator App

Goals:

- create Vite React app
- generate API client from FastAPI OpenAPI
- build workspace readiness, `/analysis`, and `/resumes` pages
- replace backend-rendered HTML pages with React routes

Deliverables:

- `apps/web/src/app`
- generated API client package
- React pages for readiness, analysis, resumes, and settings
- frontend tests for key states

Exit criteria:

- React app can display backend readiness
- `/analysis` page can run against demo data
- `/resumes` page can run against demo data

## Phase 6: Build React Extension

Goals:

- move the side panel UI to React
- isolate Chrome APIs behind extension modules
- preserve active-tab, selected-text, frame evidence, parse, direct capture, and confirm flows

Deliverables:

- React side-panel app
- MV3 manifest
- service worker
- content-script evidence collector
- extension settings module

Exit criteria:

- extension can parse a live page through the FastAPI backend
- extension can create or confirm a Job Posting
- extension stores only backend URL and capture token

## Phase 7: Port Job Posting Analysis

Goals:

- move Analysis Batch Run into FastAPI modules
- keep DeepSeek JSON behavior and evidence validation
- keep append-before-marking semantics
- stream progress to React

Deliverables:

- `GET /api/job-postings/analysis/status`
- `POST /api/job-postings/analysis/run`
- streaming adapter
- module and router tests

Exit criteria:

- demo mode can run a deterministic analysis batch
- real mode can run a DeepSeek-backed analysis batch
- one failed Job Posting does not stop the batch

## Phase 8: Port Resume Creation

Goals:

- move Resume Fit Analysis into a Python module behind one interface
- port Resume Creation orchestration
- preserve evidence sufficiency checks, claim-trace validation, note creation, PDF export, attachment-last behavior, and cleanup

Deliverables:

- `GET /api/resumes/status`
- `POST /api/resumes/create`
- Resume Fit Analysis module
- Application-Ready Resume Draft module
- PDF export module
- module and router tests

Exit criteria:

- demo mode can create a Job-Specific Resume from fixture evidence
- real mode can create a Job-Specific Resume in Notion
- cleanup behavior is tested for partial write failures

## Phase 9: Portfolio Readiness

Goals:

- make the app understandable to someone arriving from GitHub or LinkedIn
- make the demo path easy to run
- avoid exposing private user data

Deliverables:

- refreshed root `README.md`
- screenshots or short video/GIF
- `.env.example`
- demo command
- architecture diagram
- CI workflow
- release checklist

Exit criteria:

- a reviewer can run demo mode without Notion or DeepSeek credentials
- a reviewer can understand the real integration path
- all tests, type checks, and builds pass in CI

## Suggested Implementation Order

1. FastAPI app shell.
2. Pydantic schemas and OpenAPI client generation.
3. Demo workspace adapter.
4. React operator app against demo data.
5. Job Posting Capture real adapter.
6. React extension.
7. Job Posting Analysis.
8. Resume Creation.
9. Portfolio polish.

This order gives you a visible app early while keeping the hard evidence-backed workflow protected behind module interfaces.
