#!/usr/bin/env python3
"""Confirm that your token and URL work. Run this before anything else.

Prints the instance name, Home Assistant version, time zone, and how many
entities exist. If this fails, every other example fails the same way, so fix
it here where the output is short.

Message types: get_config, get_states.
"""

import argparse
import asyncio
from collections import Counter

from _env import ENV_FILE, HA_URL
from ha_ws import call, connect


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--domains",
        action="store_true",
        help="also print the entity count per domain",
    )
    args = parser.parse_args()

    print(f"connecting to {HA_URL}")
    print(f"credentials from {ENV_FILE or 'the environment'}")

    async with connect() as ws:
        config = await call(ws, {"type": "get_config"})
        states = await call(ws, {"type": "get_states"})

    print("\nauthenticated")
    print(f"  name       {config.get('location_name')}")
    print(f"  version    {config.get('version')}")
    print(f"  time zone  {config.get('time_zone')}")
    print(f"  components {len(config.get('components', []))}")
    print(f"  entities   {len(states)}")

    if args.domains:
        counts = Counter(state["entity_id"].split(".")[0] for state in states)
        print("\nentities per domain:")
        for domain, count in counts.most_common():
            print(f"  {domain:<28} {count}")


asyncio.run(main())
