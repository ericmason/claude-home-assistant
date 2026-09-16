# Dashboards as code

A Home Assistant dashboard you edit in the UI is a 3,000-line JSON blob you cannot diff, review, or roll back. Building it from a script gives you all three, and it is the difference between an agent that can help with your dashboard and one that can only describe what it would do.

The trade is real and worth stating: once a script builds the dashboard, the UI editor stops being usable for that dashboard. The next run overwrites whatever you changed.

## The builder is the source of truth

`examples/dashboards/build_dashboard.py` writes the whole config in one `lovelace/config/save`. There is no merge step, no partial update, and no attempt to preserve what is already there.

That is deliberate. A builder that merges has two sources of truth and reconciles them badly. A builder that overwrites has one, and the file is in git.

The rule that follows: **edit the script, never the dashboard**. If you change a card in the UI, it is gone the next time anyone runs the builder, and nothing warns you. Write this rule into your `CLAUDE.md` with the dashboard named, because an agent reading your repository has no way to tell a built dashboard from a hand-made one.

## The edit loop

```bash
python3 examples/dashboards/validate_dashboard.py --builder   # check it unsaved
python3 examples/dashboards/build_dashboard.py --apply        # write it
```

Validate first. The validator imports the builder, builds the config in memory, and checks it without touching the instance, so a broken entity id costs you a second rather than a broken dashboard.

Then apply. `lovelace/config/save` takes effect live. Nobody needs to restart anything, and an open browser picks the change up on the next load.

## Card helpers

Each helper returns a card dict, so a view becomes a readable list of intentions instead of eighty lines of nested JSON:

| Helper | Use for |
| --- | --- |
| `heading(text, icon)` | The title at the top of a section. |
| `entity(entity_id, name, icon)` | Lights, switches, automations, helpers. Taps toggle. |
| `status(entity_id, name)` | Binary sensors. Shows the state and when it last changed. |
| `sensor_card(entity_id, name, icon)` | A numeric sensor with its unit. |
| `grid(cards)` | Wraps a list of cards into one section. |

Anything without a helper is a raw card dict. That is fine and expected: an alarm panel or a history graph is a one-off, and inventing a helper for it buys nothing.

Views are functions returning a view dict, and `build_config()` holds the ordered list. **Position in that list is the tab order**, which is the kind of thing that is obvious in code and invisible in a UI.

## House rules a validator enforces

Conventions you cannot check are conventions you do not have. Put each one in the validator so a violation fails the build:

- **Every badge sets `show_name`.** Otherwise a badge is an icon and a bare number, and you have to remember which sensor it is.
- **No icon-only chip cards.** A row of small icon circles gives no clue what any of them track. Anything a person reads at a glance gets a name.
- **No entity is the subject of two cards in one view.** Repeating across views is fine and often deliberate, such as a pool temperature on both Home and Pool. Repeating inside one view is how a dashboard ends up showing the same TV three times.

Yours will differ. The point is that they live in `validate_dashboard.py` and exit 1, not in a document an agent skims.

## Where dashboards are stored

Every dashboard's config lives under `/config/.storage/`:

| Dashboard | URL path | Storage key |
| --- | --- | --- |
| The default one | `lovelace` | `lovelace.lovelace` |
| One you created | `my-dashboard` | `lovelace.my_dashboard` |
| An auto-generated one | varies | no file at all |

List them with `ls /config/.storage/ | grep lovelace`. A glob of `lovelace.dashboard_*` silently misses `lovelace.lovelace`, which is the default dashboard, and leaves you thinking a hand-built dashboard is auto-generated.

Read these files freely. Do not write them: Home Assistant caches the config in memory and rewrites the file from that cache, so a hand edit does nothing until a restart and can be discarded outright. See [safety.md](safety.md).

A dashboard with no stored file has never been edited. `lovelace/config` answers `config_not_found` for it, which is not an error: the strategy is generating those views on every load and there is nothing to validate.

## Creating a dashboard

```python
{"type": "lovelace/dashboards/create", "url_path": "agent-demo",
 "title": "Agent demo", "icon": "mdi:robot-outline",
 "show_in_sidebar": True, "require_admin": False, "mode": "storage"}
```

**The `url_path` must contain a hyphen.** A single-word path fails with `invalid_format: Url path needs to contain a hyphen (-)`, which at least names the problem. Add `"allow_single_word": True` to the create payload and Home Assistant skips the check, so a single-word path is possible when you want one.

`build_dashboard.py` checks for the hyphen before it connects, so you find out immediately rather than after it has done half the work.

## Adding a view to a strategy dashboard

Never click **Take control**. It converts the dashboard to a static config permanently, and every view stops auto-generating. There is no undo.

Use the strategy's `extra_views` option instead. It takes a list of full view configs that get appended to the generated ones, and it leaves the generation intact.

## Which dashboard people actually open

The frontend resolves the landing panel in this order:

1. `userData.default_panel`, per user, in `/config/.storage/frontend.user_data_<user_id>` under `core`
2. `systemData.default_panel`, for everyone, in `/config/.storage/frontend.system_data` under `core`
3. `localStorage.defaultPanel`, legacy, per device
4. `"home"`

**The key is `default_panel`, in snake case.** A camelCase `defaultPanel` in user data is ignored and the next source down wins silently, which looks exactly like the setting not taking effect.

Set the per-user value with:

```python
{"type": "frontend/set_user_data", "key": "core",
 "value": {"showAdvanced": True, "default_panel": "agent-demo"}}
```

**`set_user_data` replaces the whole `core` object.** Read it with `frontend/get_user_data` and merge first, or you drop every other setting in there, including `showAdvanced`.

Each user resolves this separately. Someone else in the house with no user-level value falls through to the system default, so they land somewhere different from you and describe a completely different dashboard when you ask them about it.

This matters more than it sounds. When several dashboards have a tab with the same name, a card added to the wrong one is invisible to the person who asked for it, and neither of you can tell why. Write down which dashboard is the real one, in your `CLAUDE.md`, with the URL path.

## Custom cards

Card packs installed through HACS, such as Mushroom or mini-graph-card, use a `custom:` type prefix. `validate_dashboard.py` lists every custom type a config uses, so you can see at a glance what a dashboard depends on.

These bundles ship minified, so card names are usually not greppable in the source. To confirm a card exists, grep the bundle for one of its config keys rather than its name.
