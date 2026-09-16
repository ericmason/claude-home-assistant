#!/usr/bin/env python3
"""Create an automation over the REST API, then read its state back.

Automations are REST-only. There is no WebSocket command that creates one:
automation/config reads, and the create path is
POST /api/config/automation/config/{id}. The same holds for scripts and scenes.
See docs/websocket-vs-rest.md.

This creates a motion-turns-on-a-light automation with a sun condition, which
is the shape most people want first.

    python3 examples/create_automation.py
    python3 examples/create_automation.py --motion binary_sensor.hall_motion \\
        --light light.hallway --apply

Without --apply this prints the YAML-equivalent config and changes nothing.

Endpoints: POST /api/config/automation/config/{id},
POST /api/services/automation/reload, GET /api/states/{entity_id}.
"""

import argparse
import json
import sys
import urllib.error

from ha_ws import rest


def build_config(automation_id, motion, light, minutes):
    """Return the automation config dict."""
    return {
        "id": automation_id,
        "alias": "Motion turns on the light after dark",
        "description": (
            "Turns the light on when motion starts after sunset, and off again "
            f"after {minutes} minutes with no motion."
        ),
        "mode": "restart",
        "triggers": [
            {"trigger": "state", "entity_id": motion, "to": "on", "id": "motion"},
            {
                "trigger": "state",
                "entity_id": motion,
                "to": "off",
                "for": {"minutes": minutes},
                "id": "clear",
            },
        ],
        "conditions": [
            {
                "condition": "or",
                "conditions": [
                    {"condition": "trigger", "id": "clear"},
                    {"condition": "sun", "after": "sunset", "before": "sunrise"},
                ],
            }
        ],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [{"condition": "trigger", "id": "motion"}],
                        "sequence": [
                            {
                                "action": "light.turn_on",
                                "target": {"entity_id": light},
                            }
                        ],
                    },
                    {
                        "conditions": [{"condition": "trigger", "id": "clear"}],
                        "sequence": [
                            {
                                "action": "light.turn_off",
                                "target": {"entity_id": light},
                            }
                        ],
                    },
                ]
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--motion",
        default="binary_sensor.garage_motion",
        help="the motion sensor that triggers it",
    )
    parser.add_argument(
        "--light", default="light.living_room", help="the light to switch"
    )
    parser.add_argument(
        "--minutes", type=int, default=5, help="minutes of no motion before off"
    )
    parser.add_argument(
        "--id",
        dest="automation_id",
        default="example_motion_light",
        help="the automation id, which becomes automation.<alias slug>",
    )
    parser.add_argument(
        "--apply", action="store_true", help="create it; otherwise preview"
    )
    args = parser.parse_args()

    config = build_config(args.automation_id, args.motion, args.light, args.minutes)

    # Confirm both entities exist first. Home Assistant happily stores an
    # automation pointing at an entity that does not exist, and it simply never
    # fires, with nothing in the log to tell you why.
    missing = []
    for entity_id in (args.motion, args.light):
        try:
            rest(f"/api/states/{entity_id}")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                missing.append(entity_id)
            else:
                raise
    if missing:
        print(f"these entities do not exist: {', '.join(missing)}")
        print("find the real ids with: python3 examples/get_states.py --match motion")
        if args.apply:
            return 1
        print("continuing the preview anyway\n")

    if not args.apply:
        print(f"would POST /api/config/automation/config/{args.automation_id}")
        print(json.dumps(config, indent=2))
        print("\ndry run; pass --apply to create it")
        return 0

    result = rest(f"/api/config/automation/config/{args.automation_id}", config)
    print(f"created: {result}")

    # Writing the config file does not load it. Reload, then read the state back:
    # a stored automation and a running one are different claims.
    rest("/api/services/automation/reload", {})
    print("reloaded automations")

    # Home Assistant derives the entity id from the alias, not from the id you
    # chose, so do not guess it. Every automation entity carries its config id
    # in attributes.id, which is the reliable way to find the one you wrote.
    states = rest("/api/states")
    for state in states:
        if not state["entity_id"].startswith("automation."):
            continue
        if state.get("attributes", {}).get("id") != args.automation_id:
            continue
        print(f"{state['entity_id']} is {state['state']}, "
              f"last triggered {state['attributes'].get('last_triggered')}")
        return 0

    print(
        f"stored, but no automation entity carries id {args.automation_id!r}. "
        "That usually means configuration.yaml does not include the file the "
        "REST API writes to. Check that it has:\n"
        "  automation: !include automations.yaml"
    )
    return 1


sys.exit(main())
