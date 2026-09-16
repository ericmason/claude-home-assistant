#!/usr/bin/env python3
"""Print everything the instance knows about: integrations, areas, devices, entities.

Run this once and keep the output. It is the map an agent needs before it can
suggest anything specific about your house, and it answers most questions about
naming without another round trip.

    python3 examples/inventory.py
    python3 examples/inventory.py --section entities
    python3 examples/inventory.py > inventory.txt

Message types: config_entries/get, config/area_registry/list,
config/device_registry/list, config/entity_registry/list, get_states.
"""

import argparse
import asyncio
from collections import defaultdict

from ha_ws import call, connect

SECTIONS = ("integrations", "areas", "devices", "entities")


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--section",
        choices=SECTIONS,
        action="append",
        help="print only this section; repeatable, defaults to all of them",
    )
    args = parser.parse_args()
    wanted = args.section or list(SECTIONS)

    async with connect() as ws:
        entries = await call(ws, {"type": "config_entries/get"})
        areas = await call(ws, {"type": "config/area_registry/list"})
        devices = await call(ws, {"type": "config/device_registry/list"})
        entities = await call(ws, {"type": "config/entity_registry/list"})
        states = await call(ws, {"type": "get_states"})

    area_names = {area["area_id"]: area["name"] for area in areas}

    if "integrations" in wanted:
        print(f"=== integrations ({len(entries)}) ===")
        for entry in sorted(entries, key=lambda item: item.get("domain") or ""):
            state = entry.get("state", "")
            flag = "" if state == "loaded" else f"  [{state}]"
            print(f"  {entry.get('domain', ''):<24} {entry.get('title', '')}{flag}")

    if "areas" in wanted:
        print(f"\n=== areas ({len(areas)}) ===")
        for area in sorted(areas, key=lambda item: item["name"]):
            print(f"  {area['name']}")
        if not areas:
            print("  none defined")

    if "devices" in wanted:
        print(f"\n=== devices ({len(devices)}) ===")
        for device in sorted(
            devices, key=lambda item: item.get("name_by_user") or item.get("name") or ""
        ):
            name = device.get("name_by_user") or device.get("name") or ""
            manufacturer = device.get("manufacturer") or ""
            area = area_names.get(device.get("area_id"), "-")
            print(f"  {name[:40]:<42} {manufacturer[:18]:<20} area={area}")

    if "entities" in wanted:
        device_area = {device["id"]: device.get("area_id") for device in devices}
        entity_area = {}
        for entity in entities:
            area_id = entity.get("area_id") or device_area.get(entity.get("device_id"))
            entity_area[entity["entity_id"]] = area_names.get(area_id, "-")

        by_domain = defaultdict(list)
        for state in states:
            by_domain[state["entity_id"].split(".")[0]].append(state)

        print(f"\n=== entities by domain ({len(states)}) ===")
        for domain in sorted(by_domain):
            print(f"\n-- {domain} ({len(by_domain[domain])})")
            for state in sorted(by_domain[domain], key=lambda item: item["entity_id"]):
                entity_id = state["entity_id"]
                friendly = state.get("attributes", {}).get("friendly_name", "")
                print(f"  {entity_id:<52} {str(state['state'])[:22]:<24} "
                      f"{friendly}  [{entity_area.get(entity_id, '-')}]")


asyncio.run(main())
