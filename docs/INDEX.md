# Documentation Index

CLIT Controller IDE is a local-first cockpit for orchestrating CLI coding
agents. This index only lists current reference docs for the working app.

## User And Product

| Document | Use it for |
| --- | --- |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Install, run, and open the app. |
| [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) | Product model, surfaces, and main workflows. |
| [FEATURE_STATUS.md](FEATURE_STATUS.md) | Current implemented feature inventory. |
| [GLOSSARY.md](GLOSSARY.md) | Project-specific terms and provider names. |

## Engineering Reference

| Document | Use it for |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System map, runtime flow, controller protocol, streaming, and recovery. |
| [BACKEND.md](BACKEND.md) | FastAPI services, controller engine, queue, state, terminals, subprocesses. |
| [FRONTEND.md](FRONTEND.md) | React app structure, Agent Dock, Tasks workbench, event store, terminal panes. |
| [API.md](API.md) | HTTP, SSE, and WebSocket endpoint reference. |
| [DATA_MODEL.md](DATA_MODEL.md) | Global and workspace JSON state files. |
| [CONFIGURATION.md](CONFIGURATION.md) | Settings, routing, command templates, Headroom, Ponytail, env vars. |
| [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | Where code and docs live. |
| [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) | Handoff guide for coding agents working in this repo. |
| [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) | Invariants and quality gates. |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local development workflow. |

## Operations, Safety, And Quality

| Document | Use it for |
| --- | --- |
| [OPERATIONS.md](OPERATIONS.md) | Runtime ports, startup/shutdown, state paths, recovery, production run. |
| [SECURITY.md](SECURITY.md) | Threat model and safety controls. |
| [TESTING.md](TESTING.md) | Backend/frontend test commands and what each suite covers. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-to-fix guide for common failures. |
| [adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md) | Auto-run policy decision record. |

## Design And Project Metadata

| Document | Use it for |
| --- | --- |
| [../DESIGN.md](../DESIGN.md) | Current UI language and component rules. |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contributor setup and PR checklist. |
| [../CHANGELOG.md](../CHANGELOG.md) | Notable project changes. |
| [PILLARS.md](PILLARS.md) | Current product guarantees encoded by tests. |
