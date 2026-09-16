# Working with an agent

Home Assistant suits an agent well. It has a complete API, everything is inspectable, and most questions are read-only. It also punishes an agent's worst habit, which is reporting that something worked because a call returned 200.

This page is about the conventions that make the difference. They are cheap, and each one exists because its absence cost somebody an afternoon.

## Give it read access first

Point the agent at `whoami.py`, `inventory.py`, `get_states.py`, `automation_trace.py`, and `render_template.py`. None of them can change anything, and together they answer most of what you will ask.

An agent that can read your instance is already useful: it can tell you why an automation did not fire, find every card pointing at a deleted entity, and explain what an integration is actually doing. Give it writes when reading stops being enough, and keep the `--apply` convention so you stay in the loop on each one.

## Write a CLAUDE.md

An agent reading your repository cannot tell which of your four dashboards you actually open, which script is the source of truth, or which button is irreversible. It will guess, reasonably, and be wrong in ways that waste your afternoon rather than its own.

`templates/CLAUDE.md` is a copyable starting point. The shape that works:

- **A table of what exists**, with a column for which one is real. Four dashboards with a tab called Lights is not a problem until a card lands on the wrong one and you cannot find it.
- **The rule**, stated as an instruction. "Add the card to Home+ first, then mirror it."
- **The prohibition**, stated as an instruction. "Never edit Home+ in the UI. The builder overwrites it."
- **A pointer to the full doc**, so the file stays short enough to be read.
- **A dated `Why:` line** naming the incident.

The `Why:` line is the part people skip and the part that makes the rule survive. A rule with no reason gets deleted in six months by someone who cannot see what it is protecting. "Why: on September 12, 2026 the card went on two dashboards but not the one Eric opens, and he could not find it for a day" does not get deleted.

Keep it short. A `CLAUDE.md` that runs to four pages is one nobody reads, agent included. One page, every line earning its place.

## Insist on the Verified block

This is the highest-value convention here.

Have the agent log its work in a changelog, with four parts:

**Problem**: what was wrong, and why the obvious fix does not work. One paragraph.

**Fix**: what changed. Exact files, entity ids, message types, routes.

**Verified**: what was actually run and what came back. Status codes, response bodies, the state the entity reported afterwards, what the log showed.

**Note**: what this did not fix, and anything discovered along the way.

`Verified` is what makes a claim of completion checkable. An agent that must write down what it ran has to run something. The difference is stark:

> Verified: created the automation.

> Verified: `POST /api/config/automation/config/example_motion_light` returned `{"result": "ok"}`. After `automation/reload`, `automation.motion_turns_on_the_light_after_dark` reads `on` with `last_triggered: null`. Triggering it manually turned `light.living_room` on, confirmed by reading `/api/states/light.living_room`, which went from `off` to `on`.

The first is a statement of intent. The second is evidence, and you can spot-check any clause of it in ten seconds.

Make it the house style. `templates/CHANGELOG.md` has a worked entry.

## Reading state back beats trusting a response

Teach the agent the same rule the examples enforce: a service call returning success means Home Assistant accepted it, not that anything happened. A light that is unplugged returns success.

`call_service.py` reads the entity back and prints before and after. Every write path should do the equivalent. When an agent says "I turned the light on", the follow-up question is always "what does the entity read now", so build the answer into the tool.

## One script per task, named verb_noun.py

`get_states.py`, `create_automation.py`, `restore_dashboard.py`. The name says what it does, so an agent scanning a directory can pick the right one without opening five files, and you can tell from a filename whether something is safe to run.

Resist the general-purpose tool with fifteen flags. A script that does one thing is a script you can read in full before running it, which is the property that matters when an agent wrote it.

## Standalone scripts, with one exception

Most scripts here are standalone. A script you can read top to bottom, in one file, is easier to check than one that resolves through four layers of a framework, and an agent that adds a task adds a file rather than editing shared code that everything else depends on.

The exception is `examples/ha_ws.py`, and it is worth naming why, because "we have one shared module" invites a second and a third:

- The authentication handshake, the id correlation, and the `max_size` setting are subtle and identical everywhere. Copied into twenty files, they get debugged twenty times, and nineteen copies keep the naive version that breaks once a subscription is open.
- It is a transport, not policy. It does not know anything about your house.

`_env.py` is the same argument for credentials: one loader means no script contains a token.

If you are about to add a third shared module, check whether you are actually building a framework. That is a different project from a directory of scripts an agent can read.

## Preview by default

Every write takes `--apply`. Without it, the script prints the exact payload and exits.

This gives you a checkpoint between the agent deciding and the agent doing, and the preview is the diff: you read the actual automation config, not a summary of it. It costs the agent nothing, since it can run the preview freely while reasoning.

See [safety.md](safety.md).

## What to put in your CLAUDE.md

Beyond the table and the rules, these save the most time:

- **Which install type you have.** Home Assistant OS, Supervised, Container, or Core. It decides whether Supervisor commands and backups work at all.
- **How to reach the host.** The SSH command, or that there is no SSH.
- **Which dashboards are built by a script**, with the script path and the "edit the script, not the dashboard" rule.
- **Anything irreversible.** Take control on a strategy dashboard is the main one.
- **Naming conventions** you already use for entities and automations.
- **What is off limits.** Locks, alarm, garage, and anything else the agent should ask about rather than act on.

## What not to give an agent

- **`core.config_entries`**, which holds every integration's credentials in plain text. If you need the agent to see one integration's config, extract that entry.
- **Your whole `.storage` directory**, for the same reason.
- **A token minted on an admin account**, when a restricted user would do. The token inherits the account's permissions, and a separate user with a limited view is a five-minute setup.
- **Backups of your dashboard configs**, if you share the repository. Each one is a complete inventory of your house.

`.gitignore` in this repository covers `backups/`, `.env`, and `secrets.yaml` for exactly these reasons.
