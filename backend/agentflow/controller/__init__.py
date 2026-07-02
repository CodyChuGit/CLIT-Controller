"""Traffic-controller engine package (CLI Interface Mythos Revamp, Workstream 2).

``chat_service`` stays the thin API-facing facade that owns CLI launches and chat
persistence; this package owns what happens after a controller CLI run finishes:

- ``engine.apply_controller_output`` — parse the single authoritative
  CLITC_RESULT_V1 block (invalid ⇒ typed failure event and NO state mutation),
  execute the validated action, or fall back to the legacy ``agentflow-*``
  directives with a compatibility-warning event. Never prefers legacy over v1.
- ``actions.execute`` — the one authoritative mutation path for a validated
  ``ControllerAction``, routed through the existing task/queue/policy/approval
  services so every gate keeps applying.
- ``context`` — prompt-context builders (workspace summary, focused-task brief).
"""
