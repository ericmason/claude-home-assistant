# Safety, enforced as code

Home Assistant runs real hardware. A bad write can leave a valve open, a lock unlocked, or a dashboard blank, and Home Assistant reports almost none of it anywhere you would look. An agent working fast makes these mistakes faster than you can read the diff.

Every rule here is enforced by something in `examples/`, because a rule that lives only in a document is a rule an agent talks itself out of. Prose asserts; code refuses.

## Preview by default, write only with --apply

Every example that changes anything prints what it would do and exits. Writing takes an explicit `--apply`.

```bash
python3 examples/call_service.py light turn_on light.living_room          # prints the call
python3 examples/call_service.py light turn_on light.living_room --apply  # makes it
```

This matters more with an agent than without one. You can read a preview in two seconds and approve it, which gives you a checkpoint between "the agent decided to do this" and "the agent did this." Without the flag, the first time you see a decision is after it took effect.

Make the preview show the actual payload, not a summary of it. `create_automation.py` prints the whole automation config, because the difference between what you meant and what it built is usually one field.

## Back up before you write, and make the rollback reversible

`build_dashboard.py` writes the previous config to `backups/` before it saves. `restore_dashboard.py` puts one back, and it backs up what it is replacing on the way.

That second part is the one people skip. A rollback that overwrites the thing you were about to want is not a rollback, it is a second mistake. Restoring is a write, so it follows the same rule as every other write.

```bash
python3 examples/dashboards/restore_dashboard.py --list
python3 examples/dashboards/restore_dashboard.py --latest --apply
```

Before anything that rewrites configuration more broadly, take a real backup:

```bash
python3 examples/backup.py --apply
```

## Validate before you save

Home Assistant does not tell you a dashboard is broken. A card pointing at a deleted entity renders as "Entity not available". A card with a bad template renders blank. Neither reaches the log. You find out when you open the dashboard on your phone, which may be weeks later.

`validate_dashboard.py` checks a config before it ships:

```bash
python3 examples/dashboards/validate_dashboard.py --builder   # what the builder would save
python3 examples/dashboards/validate_dashboard.py agent-demo  # what is live now
```

It exits 1 on failure, so it works as a gate rather than as advice. It distinguishes two cases that look alike and are not: an entity that no longer exists is a failure, and an entity that exists but is unavailable is a note. A seasonal plug being offline in August is fine; a card pointing at a device you removed in March is not.

## Read the state back instead of trusting success

`call_service` returns success when Home Assistant accepts the call, not when anything happens. A light that is unplugged returns success. A Z-Wave device that never woke up returns success. A cloud integration that timed out returns success.

`call_service.py` calls the service, waits, then reads the entity back and prints before and after. When the state did not move it says so:

```
light.living_room is currently off

call accepted, waiting 2.0s for the device
light.living_room is now off
  the state did not change. Home Assistant accepted the call, so the device or
  its integration is where to look, not your script.
```

This is the single most valuable habit to give an agent. "The service returned success" is a claim about Home Assistant's inbox. "The entity is now on" is a claim about your house.

## Never hand-edit /config/.storage

The files under `/config/.storage/` hold dashboards, config entries, the entity registry, and user data. Editing one looks like the direct route and is a trap: Home Assistant caches all of it in memory and rewrites the file from that cache. Your edit is invisible until a restart, and it is silently discarded if anything writes the same file first.

Use the API, which applies live:

```python
{"type": "lovelace/config/save", "url_path": "agent-demo", "config": {...}}
```

Reading `.storage` is fine and often the fastest way to see what is actually stored. Writing it is not.

One related trap: listing those files needs `ls /config/.storage/ | grep lovelace`, not a glob of `lovelace.dashboard_*`. The default dashboard is stored as `lovelace.lovelace`, which that glob misses, so a hand-built dashboard looks auto-generated and you conclude there is nothing to back up.

## Never click Take control on a strategy dashboard

A strategy dashboard generates its views from your entities on every load. **Take control** converts it to a static config, once, permanently. There is no undo. From then on every view is yours to maintain by hand, including the ones you liked as they were.

To add a view to a strategy dashboard, use the strategy's `extra_views` option instead. It takes a list of full view configs, appended to the generated ones, and it leaves the generation alone.

Tell your agent this explicitly. It is exactly the kind of button an agent clicks while trying to be helpful, and the damage is not visible until you notice a new device stopped showing up on its own.

## Record each gotcha with the date it bit you

When something surprises you, write it down with the date and the symptom, not only the rule. A rule without its incident gets deleted six months later by someone who cannot see why it is there. A rule with "on September 12, 2026 the card went on the wrong dashboard and I could not find it for a day" survives, because the cost is legible.

This is what the `Why:` line in `templates/CLAUDE.md` is for, and it is why `docs/` states the exact error for every gotcha rather than saying "this can fail."

## Keep credentials in a gitignored .env

No script in this repository contains a token. They all read `examples/.env`, which `.gitignore` covers, and `.env.example` is the committed template that documents the shape.

A token pasted into a script gets committed. A token in git history is a token you have to rotate, and rewriting history does not help once the repository has been cloned or pushed. Long-lived tokens do not expire on their own, so a leaked one stays good for years unless you go and revoke it.

If you already committed one: revoke it in Home Assistant first, under your profile's Security tab, and then worry about the history. Revocation is the fix. Scrubbing the history without revoking is not.

## Give read access first

Point an agent at the read-only examples before you give it anything that writes. `whoami.py`, `inventory.py`, `get_states.py`, `automation_trace.py`, and `render_template.py` cannot change your house, and they are most of what an agent needs to be useful. Most questions are answered by reading.

When you do move to writes, the `--apply` convention means the agent can still do all its reasoning and show you the payload without the flag. You add the flag.
