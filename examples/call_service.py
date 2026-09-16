#!/usr/bin/env python3
"""Call a service, then read the entity state back to prove it worked.

Home Assistant answers success true as soon as it accepts the call, not when
the device does anything. A Z-Wave switch that never woke up, a cloud
integration that timed out, a light that is unplugged all return success true.
Reading the state back afterwards is the only check that means anything.

    python3 examples/call_service.py light turn_on light.living_room
    python3 examples/call_service.py light turn_on light.living_room --apply
    python3 examples/call_service.py light turn_on light.living_room --data '{"brightness_pct": 40}' --apply

Without --apply this prints the call it would make and changes nothing.

Message types: call_service, get_states.
"""

import argparse
import asyncio
import json
import sys

from ha_ws import call, connect

SETTLE_SECONDS = 2.0


async def state_of(ws, entity_id):
    """Return one entity's state string, or None when it does not exist."""
    states = await call(ws, {"type": "get_states"})
    for state in states:
        if state["entity_id"] == entity_id:
            return state["state"]
    return None


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("domain", help="the service domain, for example light")
    parser.add_argument("service", help="the service name, for example turn_on")
    parser.add_argument("entity_id", help="the entity to target")
    parser.add_argument(
        "--data", default="{}", help="extra service data as a JSON object"
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=SETTLE_SECONDS,
        help="seconds to wait before reading the state back",
    )
    parser.add_argument(
        "--apply", action="store_true", help="make the call; otherwise preview it"
    )
    args = parser.parse_args()

    try:
        service_data = json.loads(args.data)
    except json.JSONDecodeError as error:
        sys.exit(f"--data is not valid JSON: {error}")

    message = {
        "type": "call_service",
        "domain": args.domain,
        "service": args.service,
        "service_data": service_data,
        "target": {"entity_id": args.entity_id},
    }

    async with connect() as ws:
        before = await state_of(ws, args.entity_id)
        if before is None:
            sys.exit(
                f"{args.entity_id} does not exist. Confirm the id with:\n"
                f"  python3 examples/get_states.py --match "
                f"{args.entity_id.split('.')[-1]}"
            )
        print(f"{args.entity_id} is currently {before}")

        if not args.apply:
            print("\nwould call:")
            print(json.dumps(message, indent=2))
            print("\ndry run; pass --apply to make the call")
            return

        await call(ws, message)
        print(f"\ncall accepted, waiting {args.settle}s for the device")
        await asyncio.sleep(args.settle)

        after = await state_of(ws, args.entity_id)
        print(f"{args.entity_id} is now {after}")
        if after == before:
            print(
                "  the state did not change. Home Assistant accepted the call, so "
                "the device or its integration is where to look, not your script."
            )


asyncio.run(main())
