"""Configure the linked project's production environment without logging secrets.

Vercel authentication stays in the CLI. Local bot secrets go to stdin, and the
database URL is read into memory from the connected integration. No credentials
are placed in command-line arguments or written into source files.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bingo.config import Settings  # noqa: E402
from bingo.engine import Engine  # noqa: E402


class ConfigurationError(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        raise SystemExit("Use a public HTTPS origin without a path or query.")
    project = json.loads((ROOT / ".vercel" / "project.json").read_text(encoding="utf-8"))["projectId"]
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("npm is required to run the Vercel CLI.")
    command = [npm, "exec", "--yes", "--package=vercel", "--", "vercel"]

    def run(arguments, value=None):
        result = subprocess.run(command + arguments + ["--scope", args.scope], cwd=ROOT,
                                input=value, text=True, capture_output=True, timeout=120)
        if result.returncode:
            # Environment commands can contain secrets in their output. Keep
            # their captured output private even when the CLI returns an error.
            raise ConfigurationError(f"Vercel {arguments[0]} failed (exit {result.returncode})")
        return result.stdout

    local = Settings.from_env()
    if not local.bot_token or len(local.webhook_secret) < 32:
        raise SystemExit("Configure BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET locally first.")
    variables = {"BOT_TOKEN": (local.bot_token, True),
                 "TELEGRAM_WEBHOOK_SECRET": (local.webhook_secret, True),
                 "DEMO_MODE": ("false", False), "WEBAPP_URL": (origin, False),
                 "SERVERLESS_MODE": ("true", False)}
    for name, (value, sensitive) in variables.items():
        run(["env", "add", name, "--environment", "production", "--yes", "--force",
             "--sensitive" if sensitive else "--no-sensitive"], value)
        print(f"Configured {name} for production.", flush=True)

    # Use the same environment-resolution endpoint as `vercel env pull`.
    # The deprecated list/decrypt endpoint can return encrypted envelopes.
    response = json.loads(run(["api", f"/v3/env/pull/{project}/production", "--raw"]))
    database_url = response.get("env", {}).get("DATABASE_URL", "")
    if not database_url.startswith(("postgres://", "postgresql://")):
        raise ConfigurationError("The connected database did not provide a readable production DATABASE_URL")
    settings = replace(local, database_url=database_url, demo_mode=False, serverless=True, webapp_url=origin)
    Engine(settings).ping()
    print("Verified Neon PostgreSQL and initialized the game schema.", flush=True)
    env_path = ROOT / ".env"
    content = env_path.read_text(encoding="utf-8-sig")
    pattern = r"(?m)^[ \t]*WEBAPP_URL[ \t]*=.*$"
    updated = re.sub(pattern, "WEBAPP_URL=" + origin, content) if re.search(pattern, content) else content.rstrip() + "\nWEBAPP_URL=" + origin + "\n"
    if content != updated:
        env_path.write_text(updated, encoding="utf-8")
    print("Updated the local bot launcher to use the production origin.")


if __name__ == "__main__":
    try:
        main()
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from None
    except Exception as exc:
        # Never print database URLs or subprocess environment values.
        raise SystemExit(f"Production configuration failed ({type(exc).__name__}).") from None
