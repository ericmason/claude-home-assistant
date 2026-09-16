#!/usr/bin/env python3
"""Roll a dashboard back to one of the backups in backups/.

Every write by build_dashboard.py drops a timestamped copy of the previous
config in examples/dashboards/backups/. This puts one back.

    python3 examples/dashboards/restore_dashboard.py --list
    python3 examples/dashboards/restore_dashboard.py --latest
    python3 examples/dashboards/restore_dashboard.py --latest --apply
    python3 examples/dashboards/restore_dashboard.py backups/agent-demo-20260916-140312.json --apply

Restoring is itself a write, so it backs up the config it is replacing first.
A rollback you cannot roll back is not a rollback.

Message types: lovelace/config, lovelace/config/save.
"""

import argparse
import asyncio
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ha_ws import HomeAssistantError, call, connect  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUPS = os.path.join(HERE, "backups")


def backups_for(url_path):
    """Return every backup file for a dashboard, oldest first."""
    return sorted(glob.glob(os.path.join(BACKUPS, f"{url_path}-*.json")))


def describe(path):
    """Return a one-line shape and the view titles of a backup file."""
    with open(path) as handle:
        config = json.load(handle)
    if "strategy" in config:
        views = config["strategy"].get("options", {}).get("extra_views", [])
        shape = f"strategy plus {len(views)} extra view(s)"
    else:
        views = config.get("views", [])
        cards = sum(
            len(section.get("cards", []))
            for view in views
            for section in view.get("sections", [])
        ) or sum(len(view.get("cards", [])) for view in views)
        shape = f"{len(views)} view(s), {cards} card(s)"
    return shape, [view.get("title") for view in views]


async def restore(url_path, config, apply):
    """Write a config back onto a dashboard, backing up what it replaces."""
    async with connect() as ws:
        try:
            current = await call(ws, {"type": "lovelace/config", "url_path": url_path})
        except HomeAssistantError as error:
            print(f"could not read the current config: {error}")
            current = None

        if current:
            print(f"currently live on /{url_path}: "
                  f"{len(current.get('views', []))} view(s)")

        if not apply:
            print("\ndry run; pass --apply to write it")
            return

        if current:
            os.makedirs(BACKUPS, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            path = os.path.join(BACKUPS, f"{url_path}-{stamp}.json")
            with open(path, "w") as handle:
                json.dump(current, handle, indent=2)
            print(f"backed up the config you are replacing -> {path}")

        await call(ws, {
            "type": "lovelace/config/save",
            "url_path": url_path,
            "config": config,
        })
        saved = await call(ws, {"type": "lovelace/config", "url_path": url_path})
        print(f"restored. {len(saved.get('views', []))} view(s) live")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("backup", nargs="?", help="path to a backup JSON file")
    parser.add_argument("--url-path", default="agent-demo", help="the dashboard")
    parser.add_argument("--list", action="store_true", help="list backups and exit")
    parser.add_argument("--latest", action="store_true", help="use the newest backup")
    parser.add_argument(
        "--apply", action="store_true", help="write it; otherwise dry run"
    )
    args = parser.parse_args()

    found = backups_for(args.url_path)

    if args.list or not (args.backup or args.latest):
        if not found:
            print(f"no backups for /{args.url_path} in {BACKUPS}")
            print("build_dashboard.py --apply writes one every time it saves")
            return 0
        print(f"backups for /{args.url_path}:")
        for path in found:
            shape, titles = describe(path)
            print(f"  {os.path.basename(path):<42} {shape}")
            print(f"  {'':<42} {', '.join(t for t in titles if t)}")
        if not args.list:
            print("\npick one, or use --latest")
        return 0

    if args.latest and not found:
        sys.exit(
            f"no backups for /{args.url_path} in {BACKUPS}, so there is nothing "
            "to restore. build_dashboard.py --apply writes one every time it saves."
        )

    path = found[-1] if args.latest else args.backup
    if not path or not os.path.isfile(path):
        sys.exit(f"no such backup: {path}")

    shape, titles = describe(path)
    print(f"restoring {os.path.basename(path)} -> /{args.url_path}")
    print(f"  {shape}: {', '.join(t for t in titles if t)}")
    with open(path) as handle:
        config = json.load(handle)
    asyncio.run(restore(args.url_path, config, args.apply))
    return 0


sys.exit(main())
