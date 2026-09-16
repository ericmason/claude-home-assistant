# Debugging

Home Assistant fails quietly. An automation that does not fire logs nothing. A dashboard card pointing at a deleted entity renders a placeholder and logs nothing. A template that throws renders blank and logs nothing. Almost every "it stopped working" turns out to be one of those three.

This page is the order to check things in, and the tool for each.

## The automation did not fire

Read the trace. Home Assistant records one for every automation run: what triggered it, which conditions passed, and which step it reached.

```bash
python3 examples/automation_trace.py automation.hallway_light_on_motion
```

```
automation.hallway_light_on_motion (1728394857123): 3 trace(s) in memory

  run 0a1b2c3d4e5f60718293a4b5c6d7e8f9  state=stopped
  started 2026-09-16T19:35:02.043118+00:00
  trigger   trigger/0: state of binary_sensor.hall_motion
  condition condition/0: FAILED, run stopped
```

That last line is the whole answer, and you get it without reading any YAML.

**No traces at all** means the automation has not run recently. Traces live in memory while Home Assistant runs, and a clean restart writes them to `.storage/trace.saved_traces` and restores them on startup. A crash or a power loss skips that save and loses them. Either way, an empty list does not mean the automation is broken.

**Traces exist but the trigger never fires** means the trigger is wrong, usually a `to:` or `from:` that never matches or an entity id that does not exist. Confirm the entity first:

```bash
python3 examples/get_states.py --match hall_motion
```

**A condition failed** is the most common case by a wide margin, and the trace names which one.

`trace/list` wants the automation's numeric id, not its entity id. That id is in the entity's `unique_id`, which the entity registry holds, and `automation_trace.py` looks it up for you. A YAML automation written without an `id:` has no `unique_id` and cannot be traced at all, which is a good reason to always give one.

## Did it actually happen

When you need to know whether something fired, changed, or was ever in a given state, read the history:

```
GET /api/history/period/{start_iso}?filter_entity_id=binary_sensor.hall_motion
```

This is the check to run before you believe a theory about a sensor. "The motion sensor never triggered" and "the motion sensor triggered and the automation ignored it" are different problems, and history tells you which one you have in one call.

## The template renders blank

Render it against the live engine and read the real error:

```bash
python3 examples/render_template.py "{{ states('sensor.outdoor_temperature') | float }}"
```

A bad template answers 400 with the Jinja error and a line number in the body. A template that renders but returns nothing useful usually means the entity id is wrong: `states('sensor.typo')` returns the string `unknown` rather than raising, so the failure shows up later as a card with nothing in it.

Templates inside dashboard cards are the worst case, because a failure there reaches nothing at all. `validate_dashboard.py` renders every template in a config against the live engine for exactly this reason.

## The entity id is wrong

This is the root cause often enough to check first. Entity ids change when you rename a device, and nothing that referenced the old id gets updated or complains.

```bash
python3 examples/get_states.py --match garage
python3 examples/get_states.py --unavailable
```

`--unavailable` is the fast sweep for a dead integration: an entity that exists but reports `unavailable` or `unknown` means the integration loaded and the device did not answer, which is a different problem from an entity that is gone.

To find every dead reference in a dashboard at once:

```bash
python3 examples/dashboards/validate_dashboard.py my-dashboard -v
```

## Something broke recently

Repairs are where Home Assistant puts its warnings, and they are the fastest read on what changed:

```bash
python3 examples/repairs.py
```

Deprecated YAML keys, integrations that lost their credentials, devices that vanished, and version incompatibilities all land here. Most people never look at them.

## An integration is misbehaving

When the integration depends on an add-on, the error is in the add-on's log and not in the Home Assistant log. Reach it through the Supervisor proxy, which works remotely:

```bash
python3 examples/addon_logs.py --list
python3 examples/addon_logs.py core_ssh --lines 50
```

This needs a Supervisor, so it works on Home Assistant OS and Supervised and fails with `unknown_command` on Container and Core. That failure is informative rather than a problem: it tells you which install type you have.

## The core log

For anything else, the Home Assistant log itself. Over SSH on the host:

```bash
ha core logs
ha core logs --follow
```

And before any restart, check the config parses:

```bash
ha core check
```

`ha core check` catches YAML errors that would otherwise leave you with an instance that does not come back up, which is a much worse afternoon than the one you were having. See [ssh-and-supervisor.md](ssh-and-supervisor.md).

## Debugging checklist

In the order that finds the most problems fastest:

1. Does the entity exist, and is it available? `get_states.py --match`
2. Did the thing you think happened actually happen? The history endpoint.
3. If it is an automation, what does the trace say? `automation_trace.py`
4. If it is a template, what error does the engine give? `render_template.py`
5. Is there a repair issue about it? `repairs.py`
6. If an add-on is involved, what is in its log? `addon_logs.py`
7. What does the core log say around that timestamp? `ha core logs`

Steps 1 through 4 need no SSH and no host access, and they resolve most of it.

## Make an agent do this

The habit worth teaching an agent is that a claim about your house needs evidence from your house. Not "the automation should fire now" but "the trace shows the condition passed and the action ran." Not "the service call succeeded" but "the entity reads `on`."

The `Verified:` convention in [working-with-an-agent.md](working-with-an-agent.md) is how you get that in writing.
