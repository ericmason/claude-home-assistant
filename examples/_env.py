"""Load Home Assistant credentials from a .env file into the environment.

Every other example imports HA_URL and HA_TOKEN from here, so no example ever
contains a token. Credentials are read from the first file that exists:

    1. the path in the HA_ENV_FILE environment variable, if set
    2. examples/.env
    3. .env at the repository root

Values already present in the environment win, so you can override a single
setting on the command line:

    HA_URL=http://other-instance:8123 python3 examples/whoami.py

Copy .env.example to .env and fill in your long-lived access token. The .env
file is gitignored; never commit it.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


def _candidate_paths():
    """Return the .env paths to try, in order."""
    override = os.environ.get("HA_ENV_FILE")
    paths = [override] if override else []
    paths.append(os.path.join(HERE, ".env"))
    paths.append(os.path.join(REPO_ROOT, ".env"))
    return paths


def _load_dotenv():
    """Read the first .env file that exists into os.environ."""
    for path in _candidate_paths():
        if not path or not os.path.isfile(path):
            continue
        with open(path) as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key.strip(), value)
        return path
    return None


ENV_FILE = _load_dotenv()

HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN")

if not HA_TOKEN:
    sys.exit(
        "HA_TOKEN is not set.\n"
        "  Copy .env.example to examples/.env, then paste a long-lived access\n"
        "  token from Home Assistant: click your user name in the sidebar,\n"
        "  open the Security tab, and create one under Long-lived access tokens."
    )
