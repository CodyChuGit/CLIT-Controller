# Documentation Index

CLIT Controller IDE (AgentComposer) — a local-first cockpit for orchestrating CLI
coding agents. Start with the [root README](../README.md) for the fastest path to
running it; this index routes you to the right document by task.

## Start here

| Document | When to use it |
|----------|----------------|
| [GETTING_STARTED.md](GETTING_STARTED.md) | Clone → install → run the app locally. |
| [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) | Understand what the product is and its main workflows without reading code. |
| [PILLARS.md](PILLARS.md) | The five product pillars and the interaction model — the success metrics the tests encode. |

## Product and features

| Document | When to use it |
|----------|----------------|
| [FEATURE_STATUS.md](FEATURE_STATUS.md) | What is implemented / partial / mocked / experimental / planned, with evidence. |
| [GLOSSARY.md](GLOSSARY.md) | Project-specific terms (controller, provider, directive, contract, …). |
| [cli-interface-mythos-revamp.md](cli-interface-mythos-revamp.md) | Major CLI interface refactor brief for the Agent Dock, controller backend, Antigravity terminal, and Tasks workbench. |

## Engineering

| Document | When to use it |
|----------|----------------|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Day-to-day workflow, commands, change checklist, doc-maintenance matrix. |
| [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | Where code lives and where new code belongs. |
| [FRONTEND.md](FRONTEND.md) | React/Vite app: structure, state, shared primitives, adding UI. |
| [BACKEND.md](BACKEND.md) | FastAPI backend: services, persistence, subprocess runner, adding routes. |
| [CONFIGURATION.md](CONFIGURATION.md) | Every env var and file-based config option. |
| [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) | Deterministic handoff for AI coding agents: invariants, contracts, definition of done. |
| [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) | The repository invariants and verification surface. |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Setup, checks, and review checklist for contributors. |

## Architecture and contracts

| Document | When to use it |
|----------|----------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System context, module map, control/data flow, concurrency, failure model. |
| [API.md](API.md) | HTTP/SSE/WebSocket endpoint inventory and conventions (OpenAPI at `/docs`). |
| [DATA_MODEL.md](DATA_MODEL.md) | The JSON-ledger persistence model (no database). |
| [adr/](adr/) | Architecture Decision Records (e.g. the auto-run policy). |
| [input-output-rebuild/](input-output-rebuild/) | The input/output/streaming/protocol rebuild: three planes, the CLITC_RESULT_V1 controller protocol, typed contracts, migration, verification. |

## Testing and quality

| Document | When to use it |
|----------|----------------|
| [TESTING.md](TESTING.md) | Frameworks, commands, the hermetic fixture, the pillar test suite, gaps. |

## Operations and security

| Document | When to use it |
|----------|----------------|
| [OPERATIONS.md](OPERATIONS.md) | Runtime model, run paths, state locations, recovery, troubleshooting basics. |
| [SECURITY.md](SECURITY.md) | Threat model, trust boundaries, controls, residual risks. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom → cause → fix for common failures. |

## Project status

| Document | When to use it |
|----------|----------------|
| [LIMITATIONS.md](LIMITATIONS.md) | Material limitations and technical debt, by area. |
| [ROADMAP.md](ROADMAP.md) | Proposed next work, derived from the audit and feature gaps. |
| [../CHANGELOG.md](../CHANGELOG.md) | Notable changes. |
| [audit/](audit/) | The production-hardening audit and documentation discovery/report. |

## Design notes (historical / deep-dives)

Pre-existing design documents retained for context (link, don't treat as current
spec where they diverge from code): [live-output-everywhere](live-output-everywhere.md),
[text-streaming-across-the-board](text-streaming-across-the-board.md),
[streaming-renderer-decision](streaming-renderer-decision.md),
[task-controller-io-surface](task-controller-io-surface.md),
[vscode-style-agent-dock](vscode-style-agent-dock.md),
[pwa-chrome-app-mode](pwa-chrome-app-mode.md),
[phase-1-5-product-workbench](phase-1-5-product-workbench.md),
[local-voice-io](local-voice-io.md), and [orchestrator-backend/](orchestrator-backend/).
