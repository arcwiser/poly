import os
import sys
import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import uvicorn


def main():
    host = os.environ.get("POLYLAB_HOST", "0.0.0.0")
    port = int(os.environ.get("POLYLAB_PORT", "8000"))

    print(f"""
  ┌──────────────────────────────────────────────────────┐
  │  LLVM Polymorphic Compilation Research Platform      │
  │  github.com/arcwiser/poly                            │
  └──────────────────────────────────────────────────────┘

  Listening on {host}:{port}
  Docs:        http://{host}:{port}/docs
""")

    uvicorn.run(
        "server.api:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
