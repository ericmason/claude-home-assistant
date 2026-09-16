# Home Assistant project rules

<!--
Copy this file to the root of your own Home Assistant project and edit it.
Delete anything that does not apply to you. A CLAUDE.md nobody reads is one
that grew to four pages, so keep it to one.

Each rule follows the same shape:
  a table of what exists, with a column for which one is real
  the rule, as an instruction
  the prohibition, as an instruction
  a pointer to the full doc
  a dated Why line naming the incident that made the rule necessary

The Why line is the part that makes a rule survive. Without it, someone deletes
the rule in six months because they cannot see what it protects.
-->

## Instance

- **Install type**: Home Assistant OS
- **URL**: `http://homeassistant.local:8123`
- **SSH**: `ssh -i ~/.ssh/id_ed25519 root@homeassistant.local` (Advanced SSH add-on)
- **Credentials**: `.env`, gitignored. Never paste a token into a script.

## Dashboards: <name> is the one I actually use

There are three dashboards with a Lights tab and they are built three different ways. A card added to one does not appear on the others.

| Dashboard | URL path | Built by | Do I use it |
| --- | --- | --- | --- |
| Main | `my-main` | `scripts/build_main.py`, which is the source of truth | Yes, it is the default panel on my phone |
| Overview | `lovelace` | Hand-made in the UI | Rarely |
| Auto | `dashboard-auto` | A strategy, generated on every load | Rarely |

When you add or change a dashboard card, add it to Main first by editing the builder and running `python3 scripts/build_main.py --apply`, then mirror it to the others if the feature lives there too.

Never edit Main in the UI. The next builder run overwrites it, with no warning.

Never click **Take control** on Auto. It is irreversible and stops every view from auto-generating. Use the strategy's `extra_views` option instead.

Full details in `DASHBOARDS.md`.

**Why:** on September 12, 2026 a new card went on Overview and Auto but not Main, and I could not find it for a day because Main is the only one I open.

## Writes preview by default

Every script that changes anything prints what it would do and exits. Writing requires `--apply`, which I pass, not you.

Before any write that rewrites configuration, take a backup: `python3 scripts/backup.py --apply`.

**Why:** a preview I can read in two seconds is the only checkpoint between a decision and its effect.

## Read the state back, do not trust success

`call_service` returns success when Home Assistant accepts the call, not when the device does anything. A switch that is unplugged returns success.

After any service call, read the entity back and report what it says. "The call returned success" is not a report that it worked.

**Why:** on August 29, 2026 a batch of twelve service calls all returned success and four of the devices never moved, which took a day to notice.

## Never hand-edit /config/.storage

Home Assistant caches `.storage` in memory and rewrites the files from that cache, so a hand edit is invisible until a restart and can be discarded outright. Use the API, which applies live.

Reading `.storage` is fine. Do not read `core.config_entries` unless I ask: it holds every integration's credentials in plain text.

**Why:** an edit to `lovelace.lovelace` on July 4, 2026 appeared to do nothing for an hour, then reverted.

## Restart, do not reload, after changing a custom integration

Python imports a module once per process. Reloading the integration re-runs setup with the old code still in memory, so the change has no effect and the deploy looks fine.

Deploy with `scp`, confirm with `md5sum` on both sides, then `ha core restart`.

**Why:** three rounds of "the fix is not working" on August 3, 2026 were three reloads of unchanged code.

## Confirm entity ids before writing them anywhere

An automation pointing at an entity that does not exist never fires and logs nothing. A dashboard card pointing at one renders "Entity not available" and logs nothing.

Check first: `python3 scripts/get_states.py --match <word>`.

**Why:** ten dead entity references blanked an entire dashboard view for weeks before anyone noticed.

## Ask before touching these

Locks, the alarm panel, garage doors, and irrigation valves. Read their state freely. Do not call a service on one without asking me in the same conversation.

## Log your work

Add a `CHANGELOG.md` entry for anything beyond a one-liner, using Problem / Fix / Verified / Note. The **Verified** block names what you ran and what came back: status codes, response bodies, the state the entity reported afterwards, what the log showed.

**Why:** "Verified: created the automation" is a statement of intent. A status code and a state readback is evidence I can spot-check in ten seconds.
