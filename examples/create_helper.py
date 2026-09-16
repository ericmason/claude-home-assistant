#!/usr/bin/env python3
"""Create an input_boolean helper over the WebSocket API.

Helper collections are WebSocket-only. The REST path you would guess,
POST /api/config/input_boolean/config/<id>, returns 404, and so does the
input_number and input_datetime equivalent. There is no REST route for these;
use input_boolean/create and friends instead. See docs/websocket-vs-rest.md.

    python3 examples/create_helper.py "Guest mode"
    python3 examples/create_helper.py "Guest mode" --apply

You do not choose the entity id. Home Assistant derives it by slugifying the
name, then appending _2, _3 and so on when that id is taken, so "Guest mode"
becomes input_boolean.guest_mode. This script predicts the id the same way
rather than taking one from you that the server would ignore.

Without --apply this lists the existing helpers and prints what it would create.

Message types: input_boolean/list, input_boolean/create.
"""

import argparse
import asyncio
import json
import re
import sys

from ha_ws import call, connect


def slugify(text):
    """Approximate the slug Home Assistant derives from a helper's name.

    Core lowercases and replaces every run of non-alphanumeric characters with
    a single underscore. This matches for ASCII names. A name with accents or
    non-Latin characters transliterates in ways this does not reproduce, so
    treat the preview as a prediction and trust the id the server reports back.
    """
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def next_free_id(base, taken):
    """Return base, or base_2, base_3 ... the way core dedupes a suggested id."""
    proposal = base
    attempt = 1
    while proposal in taken:
        attempt += 1
        proposal = f"{base}_{attempt}"
    return proposal


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help='the friendly name, for example "Guest mode"')
    parser.add_argument("--icon", default="mdi:toggle-switch", help="an mdi icon")
    parser.add_argument(
        "--apply", action="store_true", help="create it; otherwise preview"
    )
    args = parser.parse_args()

    base = slugify(args.name)
    if not base:
        sys.exit(f"{args.name!r} slugifies to nothing; give it a name with letters")

    payload = {"type": "input_boolean/create", "name": args.name, "icon": args.icon}

    async with connect() as ws:
        existing = await call(ws, {"type": "input_boolean/list"})
        taken = {helper.get("id") for helper in existing}

        print(f"{len(existing)} input_boolean helper(s) already exist")
        for helper in sorted(existing, key=lambda item: item.get("id", "")):
            print(f"  input_boolean.{helper.get('id')}  {helper.get('name', '')}")

        predicted = next_free_id(base, taken)

        if not args.apply:
            print(f"\nwould create input_boolean.{predicted}:")
            print(json.dumps(payload, indent=2))
            if predicted != base:
                print(f"\nnote: input_boolean.{base} is taken, so core appends a "
                      f"suffix and uses {predicted}")
            print("\ndry run; pass --apply to create it")
            return

        result = await call(ws, payload)

        # Read the id back rather than trusting the prediction. The server
        # decides, and it is the only authority on what got created.
        created = result.get("id") if isinstance(result, dict) else None
        print(f"\ncreated input_boolean.{created}")
        if created != predicted:
            print(f"  the preview predicted {predicted}, so the prediction was "
                  "wrong; the server's id is the real one")


asyncio.run(main())
