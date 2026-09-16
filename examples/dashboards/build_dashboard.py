#!/usr/bin/env python3
"""Build a dashboard from code, so the script is the source of truth.

The whole config is written in one lovelace/config/save, which applies live
with no restart. That means the script overwrites whatever is on the dashboard,
including anything you changed in the UI. That is the point: one place defines
the dashboard, and you can read it, diff it, and roll it back.

    python3 examples/dashboards/build_dashboard.py            # preview
    python3 examples/dashboards/build_dashboard.py --apply     # create and save

Before you apply, check it:

    python3 examples/dashboards/validate_dashboard.py --builder

Editing /config/.storage/lovelace.* by hand instead needs a restart, because
Home Assistant caches the config in memory. A new dashboard's url_path must
contain a hyphen, or lovelace/dashboards/create rejects it.

Message types: lovelace/dashboards/list, lovelace/dashboards/create,
lovelace/config, lovelace/config/save.
"""

import argparse
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ha_ws import HomeAssistantError, call, connect  # noqa: E402

URL_PATH = "agent-demo"
TITLE = "Agent demo"
ICON = "mdi:robot-outline"

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUPS = os.path.join(HERE, "backups")


# ---------- card helpers ----------
#
# Each helper returns a card dict. Keeping them small and named means a view is
# a readable list of intentions rather than eighty lines of nested JSON, and it
# gives the validator something to enforce house rules against.


def heading(text, icon=None):
    """A section title."""
    card = {"type": "heading", "heading": text, "heading_style": "title"}
    if icon:
        card["icon"] = icon
    return card


def entity(entity_id, name=None, icon=None, tap="toggle"):
    """A plain entity row. Use for lights, switches, automations, helpers."""
    card = {"type": "entity", "entity": entity_id, "tap_action": {"action": tap}}
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    return card


def status(entity_id, name, icon=None):
    """A binary sensor card that names what it tracks and when it last changed.

    Icon-only cards give no clue what they track, so anything a person reads at
    a glance gets a name. This uses the stock tile card so it works on any
    install. To show your own words instead of on and off, swap in a template
    card from a card pack such as Mushroom and set its secondary to a template.
    """
    card = {
        "type": "tile",
        "entity": entity_id,
        "state_content": ["state", "last_changed"],
        "tap_action": {"action": "more-info"},
    }
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    return card


def sensor_card(entity_id, name, icon=None):
    """A numeric sensor with its unit, drawn as a gauge-free tile."""
    card = {"type": "tile", "entity": entity_id, "tap_action": {"action": "more-info"}}
    if name:
        card["name"] = name
    if icon:
        card["icon"] = icon
    return card


def grid(cards, column_span=None):
    """Wrap cards into one section of a sections view."""
    section = {"type": "grid", "cards": cards}
    if column_span:
        section["column_span"] = column_span
    return section


# ---------- views ----------


def view_home(lights, sensors, binary_sensors):
    """The landing view: what you look at first."""
    sections = [
        grid([heading("Lights", "mdi:lightbulb")]
             + [entity(item) for item in lights]),
        grid([heading("Sensors", "mdi:gauge")]
             + [sensor_card(item, None) for item in sensors]),
    ]
    if binary_sensors:
        sections.append(
            grid([heading("Doors and motion", "mdi:door")]
                 + [status(item, None) for item in binary_sensors])
        )
    return {
        "type": "sections",
        "title": "Home",
        "path": "home",
        "icon": "mdi:home",
        "max_columns": 3,
        "badges": [
            # Every badge sets show_name. Without it a badge is an icon and a
            # bare number, which tells you nothing you did not already know.
            {"type": "entity", "entity": "sun.sun", "name": "Sun", "show_name": True},
        ],
        "sections": sections,
    }


def view_system(automations):
    """A second view, so the example shows more than one tab."""
    return {
        "type": "sections",
        "title": "System",
        "path": "system",
        "icon": "mdi:cog",
        "max_columns": 2,
        "sections": [
            grid([heading("Automations", "mdi:robot")]
                 + [entity(item, None, tap="more-info") for item in automations]),
            grid([
                heading("Instance", "mdi:home-assistant"),
                {"type": "markdown",
                 "content": ("Built by `examples/dashboards/build_dashboard.py`. "
                             "Edit the script, not this dashboard.")},
            ]),
        ],
    }


def build_config(lights, sensors, binary_sensors, automations):
    """Return the whole dashboard config. View order is tab order."""
    return {
        "title": TITLE,
        "views": [
            view_home(lights, sensors, binary_sensors),
            view_system(automations),
        ],
    }


# ---------- entity discovery ----------


async def pick_entities(ws, limit=6):
    """Pick a few real entities, so the example builds on any instance.

    A real builder names its entities explicitly. This one discovers them so
    that you can run it against your own install without editing it first.
    """
    states = await call(ws, {"type": "get_states"})
    by_domain = {}
    for state in states:
        domain = state["entity_id"].split(".")[0]
        by_domain.setdefault(domain, []).append(state["entity_id"])

    lights = sorted(by_domain.get("light", []) or by_domain.get("switch", []))[:limit]
    sensors = sorted(by_domain.get("sensor", []))[:limit]
    binary_sensors = sorted(by_domain.get("binary_sensor", []))[:limit]
    automations = sorted(by_domain.get("automation", []))[:limit]
    return lights, sensors, binary_sensors, automations


# ---------- transport ----------


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url-path", default=URL_PATH, help="the dashboard url path")
    parser.add_argument(
        "--apply", action="store_true", help="create and save; otherwise preview"
    )
    args = parser.parse_args()

    if "-" not in args.url_path:
        sys.exit(
            f"url_path {args.url_path!r} has no hyphen. Home Assistant requires "
            "one in a new dashboard's url path."
        )

    async with connect() as ws:
        lights, sensors, binary_sensors, automations = await pick_entities(ws)
        config = build_config(lights, sensors, binary_sensors, automations)

        cards = sum(
            len(section.get("cards", []))
            for view in config["views"]
            for section in view.get("sections", [])
        )
        print(f"{len(config['views'])} views, {cards} cards")
        for view in config["views"]:
            count = sum(len(s.get("cards", [])) for s in view["sections"])
            print(f"  {view['title']:<12} sections={len(view['sections'])} cards={count}")

        if not args.apply:
            print("\n" + json.dumps(config, indent=2)[:2000])
            print("\ndry run; pass --apply to create and save")
            return

        listing = await call(ws, {"type": "lovelace/dashboards/list"})
        existing = {board["url_path"] for board in listing}

        if args.url_path not in existing:
            await call(ws, {
                "type": "lovelace/dashboards/create",
                "url_path": args.url_path,
                "title": TITLE,
                "icon": ICON,
                "show_in_sidebar": True,
                "require_admin": False,
                "mode": "storage",
            })
            print(f"created dashboard /{args.url_path}")
        else:
            print(f"dashboard /{args.url_path} exists, backing the config up first")
            try:
                previous = await call(
                    ws, {"type": "lovelace/config", "url_path": args.url_path}
                )
            except HomeAssistantError as error:
                # config_not_found means nobody has edited this dashboard, so
                # there is no stored config to back up and saving is safe. Any
                # other error means the read failed for a reason we cannot
                # account for, and saving would overwrite a config we were
                # unable to copy. Stop rather than write without a rollback.
                if "config_not_found" not in str(error):
                    sys.exit(
                        f"could not read the current config of /{args.url_path}, "
                        f"so there would be nothing to roll back to: {error}\n"
                        "Refusing to overwrite it without a backup."
                    )
                print("no stored config yet, so there is nothing to back up")
                previous = None
            if previous:
                os.makedirs(BACKUPS, exist_ok=True)
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                path = os.path.join(BACKUPS, f"{args.url_path}-{stamp}.json")
                with open(path, "w") as handle:
                    json.dump(previous, handle, indent=2)
                print(f"backed up -> {path}")

        await call(ws, {
            "type": "lovelace/config/save",
            "url_path": args.url_path,
            "config": config,
        })

        # Read it back. A save that succeeded and a dashboard that renders are
        # not the same claim.
        saved = await call(ws, {"type": "lovelace/config", "url_path": args.url_path})
        titles = [view.get("title") for view in saved.get("views", [])]
        print(f"saved. {len(titles)} views live: {titles}")


if __name__ == "__main__":
    asyncio.run(main())
