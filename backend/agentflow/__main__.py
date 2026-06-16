"""Run Command Line Interface Terminal Controller: python -m agentflow"""

from __future__ import annotations

import os

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("AGENTFLOW_PORT", "8787"))


def main() -> None:
    print()
    print("  Command Line Interface Terminal Controller")
    print("  CLIT Controller IDE")
    print("  Vibe with CLIT Controller")
    print(f"  → http://localhost:{PORT}")
    print("  API docs → http://localhost:%d/docs" % PORT)
    print()
    uvicorn.run("agentflow.app:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
