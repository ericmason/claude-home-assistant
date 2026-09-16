#!/usr/bin/env python3
"""Take a full backup and wait for it to finish.

Run this before anything that rewrites configuration. It is the cheapest
insurance in Home Assistant and it takes one command.

    python3 examples/backup.py
    python3 examples/backup.py --apply
    python3 examples/backup.py --apply --name before-dashboard-rebuild

Three gotchas this handles, all of which cost real time to find:

  * The agent id differs by install type. Home Assistant OS and Supervised have
    hassio.local; Container and Core have backup.local. Hardcoding either one
    fails on the other half of the world, so this asks backup/agents/info at
    runtime rather than guessing.
  * backup/info does not report the agent list. It returns agent_errors,
    backups, state, and the automatic-backup timestamps, so code that reads an
    agents key off it always sees nothing. The agent list is a separate command.
  * Add-ons and folders are Supervisor-only. Ask a Core or Container install for
    them and backup/generate fails with "Addons and folders are not supported by
    core backup", so this asks get_config which install it is talking to.

Every install can take a backup. Core and Container write through the built-in
local agent, so this does not need a Supervisor.

Message types: get_config, backup/agents/info, backup/info, backup/generate.
"""

import argparse
import asyncio
import sys
import time

from ha_ws import HomeAssistantError, call, connect

# Preferred when several agents exist. Supervised installs report both, and the
# Supervisor's own agent is the one that can include add-ons.
AGENT_PREFERENCE = ("hassio.local", "backup.local")
POLL_SECONDS = 5
TIMEOUT_SECONDS = 900


def choose_agent(agents, requested=None):
    """Pick which backup agent to write to.

    agents is the list from backup/agents/info, each with an agent_id. An
    explicit request wins, and fails loudly when that agent does not exist,
    because silently writing somewhere else is worse than stopping.
    """
    available = [agent["agent_id"] for agent in agents]
    if requested:
        if requested not in available:
            sys.exit(
                f"no backup agent {requested!r} on this instance. "
                f"Available: {', '.join(available) or 'none'}"
            )
        return requested
    for preferred in AGENT_PREFERENCE:
        if preferred in available:
            return preferred
    if not available:
        sys.exit("this instance reports no backup agents, so there is nowhere to write")
    return available[0]


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", help="the backup name, defaults to a timestamp")
    parser.add_argument(
        "--agent",
        help="the backup agent id to write to; discovered when you omit it",
    )
    parser.add_argument(
        "--timeout", type=int, default=TIMEOUT_SECONDS, help="seconds to wait"
    )
    parser.add_argument(
        "--apply", action="store_true", help="take the backup; otherwise preview"
    )
    args = parser.parse_args()

    name = args.name or f"backup-{time.strftime('%Y%m%d-%H%M%S')}"

    async with connect() as ws:
        try:
            agent_info = await call(ws, {"type": "backup/agents/info"})
            info = await call(ws, {"type": "backup/info"})
        except HomeAssistantError as error:
            sys.exit(f"the backup integration did not answer: {error}")

        config = await call(ws, {"type": "get_config"})
        supervised = "hassio" in config.get("components", [])

        before = {backup["backup_id"] for backup in info.get("backups", [])}
        agents = agent_info.get("agents", [])
        agent = choose_agent(agents, args.agent)
        print(f"{len(before)} existing backup(s)")
        print(f"agents available: {', '.join(a['agent_id'] for a in agents)}")
        print(f"writing to: {agent}")

        request = {
            "type": "backup/generate",
            "agent_ids": [agent],
            "name": name,
            # Only a Supervisor can back up add-ons and the extra folders. Ask a
            # Core or Container install for either and backup/generate fails
            # with "Addons and folders are not supported by core backup".
            "include_folders": [],
            "include_all_addons": supervised,
            "include_database": True,
            "include_homeassistant": True,
        }

        if not args.apply:
            print(f"\nwould create backup {name!r} on agent {agent}")
            print("dry run; pass --apply to take it")
            return

        await call(ws, request)
        print(f"\nbackup {name!r} started, polling every {POLL_SECONDS}s")

        started = time.monotonic()
        while time.monotonic() - started < args.timeout:
            await asyncio.sleep(POLL_SECONDS)
            info = await call(ws, {"type": "backup/info"})
            backups = info.get("backups", [])
            fresh = [b for b in backups if b["backup_id"] not in before]
            elapsed = int(time.monotonic() - started)
            print(f"  [{elapsed}s] state={info.get('state')} "
                  f"backups={len(backups)} new={len(fresh)}")
            if fresh and info.get("state") in (None, "idle"):
                for backup in fresh:
                    # size lives under agents[agent_id], not on the backup
                    # itself, because one backup can sit on several agents at
                    # different sizes. A top-level backup["size"] is always None.
                    written = backup.get("agents", {}).get(agent, {})
                    size_mb = (written.get("size") or 0) / 1024 / 1024
                    print(f"\ndone: {backup['backup_id']}")
                    print(f"  name {backup.get('name')}")
                    print(f"  size {size_mb:.1f} MB on {agent}")
                    print(f"  date {backup.get('date')}")
                return

        sys.exit(f"no new backup after {args.timeout}s; check Settings > Backups")


asyncio.run(main())
