#!/usr/bin/env python3
"""List entity states, optionally filtered by substring, domain, or device class.

Use this to confirm an entity id before you write it into an automation or a
dashboard card. A card pointing at an entity that does not exist renders as
"Entity not available" and Home Assistant reports it nowhere else.

    python3 examples/get_states.py --match garage
    python3 examples/get_states.py --domain binary_sensor --device-class motion
    python3 examples/get_states.py --unavailable

Message types: get_states.
"""

import argparse
import asyncio

from ha_ws import call, connect


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--match",
        default="",
        help="only entities whose id or friendly name contains this substring",
    )
    parser.add_argument("--domain", help="only this domain, for example light")
    parser.add_argument(
        "--device-class",
        help="only entities with this device_class, for example temperature",
    )
    parser.add_argument(
        "--unavailable",
        action="store_true",
        help="only entities that are unavailable or unknown",
    )
    parser.add_argument(
        "--attributes",
        action="store_true",
        help="print every attribute of each matching entity",
    )
    args = parser.parse_args()

    async with connect() as ws:
        states = await call(ws, {"type": "get_states"})

    needle = args.match.lower()
    matches = []
    for state in states:
        entity_id = state["entity_id"]
        attributes = state.get("attributes", {})
        name = attributes.get("friendly_name", "")
        if args.domain and entity_id.split(".")[0] != args.domain:
            continue
        if args.device_class and attributes.get("device_class") != args.device_class:
            continue
        if args.unavailable and state["state"] not in ("unavailable", "unknown"):
            continue
        if needle and needle not in entity_id.lower() and needle not in name.lower():
            continue
        matches.append(state)

    print(f"{len(matches)} of {len(states)} entities match")
    for state in sorted(matches, key=lambda item: item["entity_id"]):
        attributes = state.get("attributes", {})
        unit = attributes.get("unit_of_measurement", "")
        value = f"{state['state']}{' ' + unit if unit else ''}"
        print(f"  {state['entity_id']:<52} {value[:24]:<26} "
              f"{attributes.get('friendly_name', '')}")
        if args.attributes:
            for key, attribute in sorted(attributes.items()):
                print(f"      {key}: {attribute}")


asyncio.run(main())
