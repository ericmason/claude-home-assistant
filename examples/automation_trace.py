#!/usr/bin/env python3
"""Find out why an automation did or did not do what you expected.

Home Assistant records a trace for every automation run: what triggered it,
which conditions passed, and which step it reached. This is the answer to
"the automation did not fire", and it beats guessing at the YAML.

    python3 examples/automation_trace.py automation.hallway_light_on_motion
    python3 examples/automation_trace.py automation.hallway_light_on_motion --runs 10
    python3 examples/automation_trace.py automation.hallway_light_on_motion --raw

If the list comes back empty, the automation has not run recently. Traces live
in memory while Home Assistant runs, and a clean restart saves them to
.storage/trace.saved_traces and restores them on the way back up. A crash or a
power loss skips that save, so those lose every trace.

Message types: trace/list, trace/get.
"""

import argparse
import asyncio
import json
import sys

from ha_ws import HomeAssistantError, call, connect


def summarize(trace):
    """Print the trigger, the condition results, and the last step reached."""
    steps = trace.get("trace", {})
    config = trace.get("config", {})

    print(f"\n  run {trace.get('run_id')}  state={trace.get('state')}")
    print(f"  started {trace.get('timestamp', {}).get('start')}")
    if trace.get("error"):
        print(f"  ERROR {trace['error']}")

    context = trace.get("context", {})
    if context.get("parent_id"):
        print(f"  parent context {context['parent_id']}")

    for path in sorted(steps):
        entries = steps[path]
        if not entries:
            continue
        entry = entries[0]
        label = path
        if path.startswith("trigger"):
            variables = entry.get("changed_variables", {}).get("trigger", {})
            description = variables.get("description") or variables.get("platform", "")
            print(f"  trigger   {label}: {description}")
        elif path.startswith("condition"):
            passed = entry.get("result", {}).get("result")
            print(f"  condition {label}: {'passed' if passed else 'FAILED, run stopped'}")
        elif path.startswith("action"):
            print(f"  action    {label}: {entry.get('result', {})}")

    if not steps:
        print("  the trace has no steps recorded")

    alias = config.get("alias")
    if alias:
        print(f"  automation: {alias}")


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "entity_id",
        help="the automation entity id, for example automation.porch_light",
    )
    parser.add_argument(
        "--runs", type=int, default=3, help="how many recent runs to detail"
    )
    parser.add_argument(
        "--raw", action="store_true", help="dump the full trace JSON instead"
    )
    args = parser.parse_args()

    async with connect() as ws:
        # trace/list wants the automation's numeric id, not its entity id. It is
        # in the entity's unique_id, which the entity registry holds.
        try:
            registry = await call(
                ws, {"type": "config/entity_registry/get", "entity_id": args.entity_id}
            )
        except HomeAssistantError as error:
            if "not_found" in str(error):
                sys.exit(
                    f"no entity {args.entity_id} in the registry. Check the "
                    "entity id, and remember it is the automation entity "
                    "(automation.something), not the alias."
                )
            raise
        automation_id = registry.get("unique_id")
        if not automation_id:
            sys.exit(
                f"{args.entity_id} has no unique_id, so it is a YAML automation "
                "without an id: and Home Assistant cannot trace it. Give it an "
                "id: in automations.yaml."
            )

        traces = await call(
            ws, {"type": "trace/list", "domain": "automation", "item_id": automation_id}
        )
        print(f"{args.entity_id} ({automation_id}): {len(traces)} trace(s) in memory")
        if not traces:
            print("  none. It has not run recently, or the last stop was a")
            print("  crash, which loses traces that a clean restart keeps.")
            return

        for stub in traces[: args.runs]:
            detail = await call(
                ws,
                {
                    "type": "trace/get",
                    "domain": "automation",
                    "item_id": automation_id,
                    "run_id": stub["run_id"],
                },
            )
            if args.raw:
                print(json.dumps(detail, indent=2))
            else:
                summarize(detail)


asyncio.run(main())
