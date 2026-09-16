#!/usr/bin/env python3
"""Check a dashboard config before or after you save it.

Home Assistant does not report a broken card anywhere a person would see it. A
card pointing at a deleted entity renders as "Entity not available", a card with
a bad template renders blank, and the log says nothing. This catches those
before they ship.

    python3 examples/dashboards/validate_dashboard.py lovelace
    python3 examples/dashboards/validate_dashboard.py --builder
    python3 examples/dashboards/validate_dashboard.py lovelace -v

What it checks:

  * entities that do not exist, which is a failure
  * entities that exist but are unavailable, which is reported, not failed,
    because a seasonal plug being offline in August is fine
  * Jinja templates, rendered against the live engine
  * the same entity as the subject of two cards in one view
  * house rules: every badge sets show_name, no icon-only chip cards

Exit code is 1 when anything failed, so it works as a pre-save gate.

Message types: lovelace/config, get_states.
Endpoint: POST /api/template.
"""

import argparse
import asyncio
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ha_ws import HomeAssistantError, call, connect, rest  # noqa: E402

SKIP_KEYS = ("tap_action", "hold_action", "double_tap_action")


async def live_config(url_path):
    """Read a dashboard's saved config over the WebSocket API.

    config_not_found has two causes and the error does not distinguish them. A
    dashboard nobody has edited has no stored config, so Home Assistant answers
    config_not_found rather than returning the view list it is generating, and
    there is nothing to validate: the strategy rebuilds those views from your
    entities on every load. A url path that does not exist at all answers the
    same way, so read the message as "no config here" and not as "this is a
    strategy dashboard".
    """
    async with connect() as ws:
        try:
            return await call(ws, {"type": "lovelace/config", "url_path": url_path})
        except HomeAssistantError as error:
            if "config_not_found" in str(error):
                sys.exit(
                    f"/{url_path} has no stored config. Either the url path "
                    "does not exist, so check it for a typo, or the dashboard "
                    "is auto-generated and there is nothing to check. Run "
                    "lovelace/dashboards/list to see which. Validate a "
                    "dashboard you built, or pass --builder."
                )
            raise


async def builder_config():
    """Build the config the builder would save, without saving it.

    Importing the builder gives you the exact dict it is about to write, so you
    can check it before it touches the instance.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_dashboard

    async with connect() as ws:
        entities = await build_dashboard.pick_entities(ws)
    return build_dashboard.build_config(*entities)


def card_subjects(view):
    """Return the entity each card in a view is about, from its `entity` field.

    Ignores badges and tap targets. Those repeat an entity for structural
    reasons and are not the duplication worth flagging.
    """
    subjects = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("type"), str) and isinstance(node.get("entity"), str):
                subjects.append(node["entity"])
            for key, value in node.items():
                if key in SKIP_KEYS:
                    continue
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(view.get("sections", view.get("cards", [])))
    return subjects


def collect(config):
    """Pull every entity reference, template, card type, and badge out of a config."""
    entities, templates, types, badges = [], set(), set(), []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("type"), str):
                types.add(node["type"])
            for key, value in node.items():
                if key == "badges" and isinstance(value, list):
                    badges.extend(item for item in value if isinstance(item, dict))
                    walk(value)
                elif key == "entity" and isinstance(value, str):
                    entities.append(value)
                elif key == "entities" and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            entities.append(item)
                        else:
                            walk(item)
                elif key == "entity_id":
                    entities.extend([value] if isinstance(value, str) else value or [])
                elif isinstance(value, str) and "{{" in value:
                    templates.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(config)
    return entities, templates, types, badges


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "url_path", nargs="?", default="lovelace", help="the dashboard to read"
    )
    parser.add_argument(
        "--builder",
        action="store_true",
        help="check what build_dashboard.py would save, unsaved",
    )
    parser.add_argument(
        "--strict-duplicates",
        action="store_true",
        help="treat a repeat within one view as a failure, not a note",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="list every unavailable entity"
    )
    args = parser.parse_args()

    if args.builder:
        config = await builder_config()
        label = "build_dashboard.py"
    else:
        config = await live_config(args.url_path)
        label = f"/{args.url_path} (live)"

    if "strategy" in config:
        # A strategy dashboard generates its own views. Only extra_views are
        # yours to check; the rest are rebuilt on every load.
        views = config.get("strategy", {}).get("options", {}).get("extra_views", [])
        print(f"{label}: strategy dashboard, {len(views)} extra view(s)")
    else:
        views = config.get("views", [])
        print(f"{label}: {len(views)} view(s)")

    entities, templates, types, badges = collect(config)

    async with connect() as ws:
        states = {state["entity_id"]: state for state in await call(
            ws, {"type": "get_states"}
        )}

    failures = 0

    print(f"\nentities: {len(set(entities))} distinct, {len(entities)} reference(s)")
    missing = sorted({item for item in entities if item not in states})
    if missing:
        failures += len(missing)
        print(f"  FAIL  {len(missing)} entity(s) do not exist:")
        for item in missing:
            print(f"          {item}")
    else:
        print("  ok    every entity exists")

    unavailable = sorted(
        {item for item in entities
         if item in states and states[item]["state"] in ("unavailable", "unknown")}
    )
    if unavailable:
        suffix = ":" if args.verbose else " (-v to list)"
        print(f"  note  {len(unavailable)} unavailable or unknown right now{suffix}")
        if args.verbose:
            for item in unavailable:
                print(f"          {item:<58} {states[item]['state']}")

    repeats = {}
    for view in views:
        subjects = card_subjects(view)
        for item in set(subjects):
            if subjects.count(item) > 1:
                repeats.setdefault(view.get("title", "?"), []).append(
                    (item, subjects.count(item))
                )
    if repeats:
        word = "FAIL" if args.strict_duplicates else "note"
        if args.strict_duplicates:
            failures += sum(len(value) for value in repeats.values())
        print(f"  {word}  the same entity is the subject of two cards in one view:")
        for title, items in repeats.items():
            for item, count in sorted(items, key=lambda pair: -pair[1]):
                print(f"          {title:<14} {item:<48} x{count}")
    else:
        print("  ok    no entity repeats within a single view")

    across = sum(1 for item in set(entities) if entities.count(item) > 1)
    print(f"  note  {across} entity(s) appear on more than one view, which is allowed")

    print(f"\ntemplates: {len(templates)}")
    broken = []
    for template in sorted(templates):
        try:
            rest("/api/template", {"template": template})
        except urllib.error.HTTPError as error:
            broken.append((template, error.read().decode(errors="replace")))
    if broken:
        failures += len(broken)
        print(f"  FAIL  {len(broken)} template(s) do not render:")
        for template, detail in broken:
            print(f"          {template[:90]}\n            {detail[:160]}")
    elif templates:
        print("  ok    all render against the live engine")
    else:
        print("  ok    none to check")

    print("\nhouse rules:")
    chips = [item for item in types if item.endswith("chips-card")]
    if chips:
        failures += len(chips)
        print(f"  FAIL  chip card in use ({', '.join(chips)}); chips are icon-only "
              "and give no clue what they track")
    else:
        print("  ok    no chip cards")

    unnamed = [badge for badge in badges if not badge.get("show_name")]
    if unnamed:
        failures += len(unnamed)
        print(f"  FAIL  {len(unnamed)} badge(s) without show_name:")
        for badge in unnamed:
            print(f"          {badge.get('entity', badge)}")
    else:
        print(f"  ok    all {len(badges)} badge(s) show a name")

    custom = sorted(item for item in types if item.startswith("custom:"))
    print(f"\ncustom cards used: {', '.join(custom) if custom else 'none'}")
    print(f"\n{'FAILED' if failures else 'PASSED'}: {failures} problem(s)")
    return 1 if failures else 0


sys.exit(asyncio.run(main()))
