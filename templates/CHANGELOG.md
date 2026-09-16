# Changelog

<!--
Copy this file into your own project. Newest entries at the top.

Two entry shapes coexist. Small changes get a dated bullet. Anything with a
cause worth remembering gets a titled section with four parts:

  Problem   what was wrong, and why the obvious fix does not work
  Fix       what changed: exact files, entity ids, message types, routes
  Verified  what you ran and what came back
  Note      what this did not fix, and what you found along the way

Verified is the part that matters. It is what turns a claim of completion into
something checkable. An agent that has to write down what it ran has to run
something. Be specific: status codes, response bodies, the state an entity
reported afterwards, what the log showed, how long a request took.
-->

## 2026-09-16

### Motion light never fired after the hallway sensor was replaced

**Problem:** `automation.hallway_light_on_motion` stopped turning the light on after the old motion sensor was swapped for a new one. Nothing in the log, and the automation showed as `on` in the UI, which is the state of the automation and not a statement about whether it works. The obvious fix, reloading automations, does nothing here: the config is valid and loads fine. It refers to an entity that no longer exists, and Home Assistant treats that as a trigger that never matches.

**Fix:**

- Repointed the trigger in `automations.yaml` from `binary_sensor.hall_motion` to `binary_sensor.hallway_motion_occupancy`, which is what the replacement device registered as.
- Repointed the same entity in the Home view of `scripts/build_main.py`, in the `status()` call in `view_home()`.
- Ran `python3 scripts/validate_dashboard.py --builder` before saving, which checks every entity the builder references against the live state list. It now passes, so the next stale reference fails the build instead of shipping.

**Verified:**

- `python3 scripts/get_states.py --match motion` confirms `binary_sensor.hall_motion` is gone and `binary_sensor.hallway_motion_occupancy` exists, reading `off`.
- `POST /api/config/automation/config/hallway_light_on_motion` returned `{"result": "ok"}`, and `POST /api/services/automation/reload` returned `200` with an empty body.
- Walked past the sensor. `python3 scripts/automation_trace.py automation.hallway_light_on_motion` shows one trace, `state=stopped`, with `trigger/0: state of binary_sensor.hallway_motion_occupancy` and `action/0` calling `light.turn_on`.
- `GET /api/states/light.living_room` went from `off` before to `on` after, with `last_changed` matching the trace timestamp to the second.
- `python3 scripts/validate_dashboard.py --builder` passes with 0 problems. Before the dashboard fix it reported `FAIL 1 entity(s) do not exist: binary_sensor.hall_motion`, which is the mutation test that the new check actually catches this.

**Note:** the off half of the automation is untested, since it needs five minutes of no motion. The trace for it will not exist until then. Two other automations still reference `binary_sensor.hall_motion` and were left alone, because both are disabled and slated for deletion: `automation.old_porch_test` and `automation.motion_debug`.

## 2026-09-14

- Added `--unavailable` to `scripts/get_states.py` to sweep for dead integrations in one call.
- Bumped `max_size` to 32 MiB in `scripts/ha_ws.py`. `backup/info` on this instance now returns 1.4 MB and was about to cross the old cap, which closes the connection with `message too big` rather than raising something catchable.
