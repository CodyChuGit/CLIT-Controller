"""Native Context Intelligence System (Phase 1: preview/benchmark only).

A typed, deterministic pipeline that turns a user task into an explained,
token-measured prompt package — without touching any live prompt path
(``chat_service`` / ``prompt_templates`` are deliberately not imported here).

Entry points: ``pipeline.run_preview`` and ``benchmarks.run_benchmark``.
"""
