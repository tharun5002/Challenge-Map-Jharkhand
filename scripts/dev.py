#!/usr/bin/env python3
"""Start the API and the Next.js dev server with one command.

Usage::

    cp .env.example .env      # once, then edit JWT_SECRET etc.
    python scripts/dev.py     # or: make dev

The launcher reads the project ``.env`` through ``api.config.load_env_file`` (the
same loader the API uses), starts uvicorn, waits for ``/api/v1/health`` to answer
before starting the web app, and stops both process trees on Ctrl+C. No Docker,
no Postgres and no extra dependency is required.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api.config import load_env_file  # noqa: E402

VENV_PYTHONS = (
    Path(".venv313") / "Scripts" / "python.exe",
    Path(".venv313") / "bin" / "python",
    Path(".venv312") / "Scripts" / "python.exe",
    Path(".venv312") / "bin" / "python",
)


def resolve_python() -> Path:
    """Prefer the project virtualenv; fall back to the interpreter running this file."""
    for relative in VENV_PYTHONS:
        candidate = PROJECT_ROOT / relative
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def wait_for_health(url: str, timeout: float, process: subprocess.Popen) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def terminate_tree(process: subprocess.Popen) -> None:
    """Stop a process and its children (uvicorn reloader, npm/node)."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        process.terminate()


def positive_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the FastAPI service and the Next.js app together."
    )
    parser.add_argument("--api-port", type=positive_port, default=8000)
    parser.add_argument("--web-port", type=positive_port, default=3000)
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="start only the API (useful for /docs or the test client)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the commands and exit without starting anything",
    )
    args = parser.parse_args()

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        print(
            "Missing .env in the project root.\n"
            "Run:  cp .env.example .env\n"
            "then set JWT_SECRET, CHALLENGEMAP_BOOTSTRAP_ADMIN, and "
            "CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL before starting.",
            file=sys.stderr,
        )
        return 1

    loaded = load_env_file(env_path)
    api_base = os.environ.get(
        "NEXT_PUBLIC_API_BASE", f"http://127.0.0.1:{args.api_port}"
    )
    os.environ.setdefault("NEXT_PUBLIC_API_BASE", api_base)

    python = resolve_python()
    api_command = [
        str(python),
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.api_port),
    ]
    web_command = ["npm", "run", "dev", "--", "--port", str(args.web_port)]

    if args.dry_run:
        print(f"Loaded {loaded} variable(s) from .env")
        print(f"API : {' '.join(api_command)}")
        print(f"Web : {' '.join(web_command)}  (cwd=frontend)")
        print(f"NEXT_PUBLIC_API_BASE={os.environ['NEXT_PUBLIC_API_BASE']}")
        return 0

    spawn = {
        "env": os.environ.copy(),
        "start_new_session": os.name != "nt",
    }
    api = subprocess.Popen(api_command, cwd=str(PROJECT_ROOT), **spawn)
    processes = [api]

    try:
        health_url = f"http://127.0.0.1:{args.api_port}/api/v1/health"
        if not wait_for_health(health_url, timeout=30, process=api):
            print(
                "The API did not become healthy on "
                f"{health_url}. Check the traceback above.",
                file=sys.stderr,
            )
            return 1
        print(f"API ready  -> http://127.0.0.1:{args.api_port}  (docs at /docs)")
        print(f"Web        -> NEXT_PUBLIC_API_BASE={os.environ['NEXT_PUBLIC_API_BASE']}")

        if args.no_web:
            print("API only. Press Ctrl+C to stop.")
            api.wait()
            return api.returncode or 0

        if os.name == "nt":
            web = subprocess.Popen(
                f'npm run dev -- --port {args.web_port}',
                cwd=str(PROJECT_ROOT / "frontend"),
                shell=True,
                **spawn,
            )
        else:
            web = subprocess.Popen(
                web_command, cwd=str(PROJECT_ROOT / "frontend"), **spawn
            )
        processes.append(web)
        print(f"Web ready  -> http://localhost:{args.web_port}")
        print("Press Ctrl+C to stop both.")

        while all(process.poll() is None for process in processes):
            time.sleep(1)
        return 1 if any(process.poll() not in (0, None) for process in processes) else 0

    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for process in reversed(processes):
            terminate_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
