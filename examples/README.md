# Examples

Run `whoami.py` first. If it fails, everything else fails the same way and its output is shorter.

Every example needs `examples/.env`. Copy `.env.example` from the repository root and fill in your URL and token. See [getting-connected.md](../docs/getting-connected.md).

## Read-only

Nothing here can change your instance.

| Script | What it does |
| --- | --- |
| `whoami.py` | Confirms your token works. Prints the version, time zone, and entity count. **Run this first.** |
| `inventory.py` | Every integration, area, device, and entity grouped by domain. Run it once and keep the output. |
| `get_states.py` | Filters entity states by substring, domain, device class, or availability. Use it to confirm an entity id. |
| `automation_trace.py` | Why an automation did or did not fire: the trigger, each condition result, and the last step reached. |
| `render_template.py` | Renders a Jinja template against the live engine, so you see the real error rather than a blank card. |
| `repairs.py` | Open repair issues, which is where Home Assistant hides its warnings. |
| `addon_logs.py` | Lists Supervisor add-ons and reads one's log. Needs a Supervisor, so it fails on Container and Core. |

## Writes, which need --apply

Each one previews the exact payload and exits. Nothing is written without the flag.

| Script | What it does |
| --- | --- |
| `call_service.py` | Calls a service, then reads the entity back and prints before and after. |
| `create_helper.py` | Creates an `input_boolean` over the WebSocket API, which is the only API that can. |
| `create_automation.py` | Creates an automation over REST, reloads, then finds it by its config id and reports its state. |
| `backup.py` | Takes a full backup and polls until it finishes. Works on every install type, because it discovers the backup agent at runtime. |

## Dashboards

The three together are a complete safe write loop: preview, validate, back up, write, roll back.

| Script | What it does |
| --- | --- |
| `dashboards/build_dashboard.py` | Builds a two-view dashboard from code and saves it in one call. Backs up the previous config first. |
| `dashboards/validate_dashboard.py` | Checks a config for dead entities, broken templates, duplicates, and house rules. Exits 1 on failure. |
| `dashboards/restore_dashboard.py` | Lists and restores backups. Restoring backs up what it replaces. |

## Shell

| Script | What it does |
| --- | --- |
| `shell/call_service.sh` | POSIX sh with curl and jq. Turns switches on for N minutes and restores their original state on every exit path, including Ctrl-C. |

## Shared modules

Everything else is standalone. These two are the exception, and [working-with-an-agent.md](../docs/working-with-an-agent.md) explains why.

| Module | What it does |
| --- | --- |
| `_env.py` | Loads `HA_URL` and `HA_TOKEN` from `.env`, so no script contains a credential. |
| `ha_ws.py` | Connects and authenticates, correlates replies by id, raises on failure, and raises the frame size cap. Also holds `rest()`. |
