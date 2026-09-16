#!/usr/bin/env python3
"""List Supervisor add-ons and read one add-on's log.

When an integration depends on an add-on, the add-on's log holds the error and
the Home Assistant log does not. Reaching it needs the Supervisor, which the
WebSocket API proxies, so you do not need to be on the host.

    python3 examples/addon_logs.py --list
    python3 examples/addon_logs.py core_ssh
    python3 examples/addon_logs.py core_ssh --lines 50

Only Home Assistant OS and Supervised installs have a Supervisor. On Home
Assistant Container or Core this fails, which is expected.

Message types: supervisor/api.
Endpoint: GET /api/hassio/addons/{slug}/logs.
"""

import argparse
import asyncio
import sys
import urllib.error

from ha_ws import HomeAssistantError, call, connect, rest


async def list_addons():
    """Return the installed add-ons through the Supervisor proxy."""
    async with connect() as ws:
        result = await call(
            ws,
            {"type": "supervisor/api", "endpoint": "/addons", "method": "get"},
        )
    return result.get("addons", [])


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slug", nargs="?", help="the add-on slug, for example core_ssh")
    parser.add_argument("--list", action="store_true", help="list add-ons and exit")
    parser.add_argument(
        "--lines", type=int, default=30, help="how many trailing log lines to print"
    )
    args = parser.parse_args()

    try:
        addons = await list_addons()
    except HomeAssistantError as error:
        sys.exit(
            f"{error}\nThis install has no Supervisor, so there are no add-ons. "
            "That is normal on Home Assistant Container and Core."
        )

    if args.list or not args.slug:
        print(f"{len(addons)} add-on(s) installed")
        for addon in sorted(addons, key=lambda item: item["slug"]):
            state = addon.get("state", "")
            print(f"  {addon['slug']:<34} {state:<10} {addon.get('name', '')}")
        if not args.slug:
            print("\npass a slug to read its log")
        return

    # The log endpoint returns plain text, not JSON, so rest() hands back a str.
    try:
        log = rest(f"/api/hassio/addons/{args.slug}/logs")
    except urllib.error.HTTPError as error:
        sys.exit(f"HTTP {error.code} reading the log for {args.slug}: {error.reason}")

    lines = str(log).splitlines()
    print(f"{args.slug}: last {min(args.lines, len(lines))} of {len(lines)} line(s)")
    for line in lines[-args.lines:]:
        print(f"  {line}")


asyncio.run(main())
