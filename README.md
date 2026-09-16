# Claude and Home Assistant

A working setup for pointing Claude Code, or any coding agent, at a real Home Assistant install: runnable examples, the API boundaries that are not documented anywhere, and the conventions that keep an agent from breaking your house.

Home Assistant suits an agent well. It has a complete API, everything is inspectable, and most questions are read-only. It also punishes an agent's worst habit, which is reporting that something worked because a call returned 200. The examples here are built around that: every write previews first, and every write reads the state back afterwards.

This grew out of running Claude Code against a real Home Assistant install for a year. Every gotcha documented here is one that cost an afternoon.

## Who this is for

You run Home Assistant, you have Claude Code or a similar agent, and you want the agent to do more than describe what it would do. You do not need to have written anything against the Home Assistant API before.

You need Python 3.11 or newer, a Home Assistant instance you administer, and about ten minutes. Use Home Assistant 2024.10 or newer. The automation examples write the plural `triggers` and `actions` keys, which arrived in that release.

## Quickstart

1. **Create a long-lived access token.** In Home Assistant, click your user name at the bottom of the sidebar, open the **Security** tab, scroll to **Long-lived access tokens**, and create one. It is shown once.

2. **Set up your credentials.**

   ```bash
   git clone https://github.com/ericmason/claude-home-assistant.git
   cd claude-home-assistant
   cp .env.example examples/.env
   ```

   Edit `examples/.env` with your URL and the token.

3. **Install the one dependency.**

   ```bash
   pip install -r requirements.txt
   ```

4. **Confirm it works.**

   ```bash
   python3 examples/whoami.py
   ```

5. **Take an inventory and keep it.**

   ```bash
   python3 examples/inventory.py > inventory.txt
   ```

   That file is the map your agent needs before it can say anything specific about your house.

## Docs

| Doc | What it covers |
| --- | --- |
| [getting-connected.md](docs/getting-connected.md) | Tokens, `.env`, the first two commands to run, and what each failure message means. |
| [websocket-vs-rest.md](docs/websocket-vs-rest.md) | Which API serves what, with the exact error each wrong guess gives you. The most useful page here. |
| [safety.md](docs/safety.md) | The conventions that keep a write from becoming an incident, each enforced by code rather than asserted. |
| [dashboards-as-code.md](docs/dashboards-as-code.md) | Building a dashboard from a script, validating before you save, and which dashboard people actually open. |
| [debugging.md](docs/debugging.md) | Traces, templates, history, add-on logs, and the order to check them in. |
| [ssh-and-supervisor.md](docs/ssh-and-supervisor.md) | Host access, `ha core check`, reading `.storage`, and deploying a custom integration. |
| [custom-integrations.md](docs/custom-integrations.md) | A minimal worked integration, with the lifecycle facts that are not obvious. |
| [exposing-to-the-internet.md](docs/exposing-to-the-internet.md) | The same guest-access feature built safely and unsafely, plus a review checklist. |
| [working-with-an-agent.md](docs/working-with-an-agent.md) | What to put in your `CLAUDE.md`, the changelog convention, and what not to hand an agent. |

## Examples

Read-only, so none of these can change anything:

| Script | What it does |
| --- | --- |
| [`whoami.py`](examples/whoami.py) | Confirms your token works. Run this first. |
| [`inventory.py`](examples/inventory.py) | Every integration, area, device, and entity. |
| [`get_states.py`](examples/get_states.py) | Filters states by substring, domain, device class, or availability. |
| [`automation_trace.py`](examples/automation_trace.py) | Why an automation did or did not fire. |
| [`render_template.py`](examples/render_template.py) | Renders a template against the live engine. |
| [`repairs.py`](examples/repairs.py) | Open repair issues. |
| [`addon_logs.py`](examples/addon_logs.py) | Lists add-ons and reads one's log. |
| [`dashboards/validate_dashboard.py`](examples/dashboards/validate_dashboard.py) | Checks a dashboard config before you save it. Exits 1 on failure. |

Writes, which preview by default and need `--apply`:

| Script | What it does |
| --- | --- |
| [`call_service.py`](examples/call_service.py) | Calls a service, then reads the entity back. |
| [`create_helper.py`](examples/create_helper.py) | Creates an `input_boolean` over WebSocket. |
| [`create_automation.py`](examples/create_automation.py) | Creates an automation over REST, then confirms it loaded. |
| [`backup.py`](examples/backup.py) | Takes a full backup and waits for it. |
| [`dashboards/build_dashboard.py`](examples/dashboards/build_dashboard.py) | Builds a dashboard from code, backing up the previous config. |
| [`dashboards/restore_dashboard.py`](examples/dashboards/restore_dashboard.py) | Rolls a dashboard back. |

One example writes as soon as you run it, so it gets its own row:

| Script | What it does |
| --- | --- |
| [`shell/call_service.sh`](examples/shell/call_service.sh) | A curl and jq version with no `--apply` flag. It turns a switch on, waits, and restores the original state on every exit path. |

Copyable templates for your own project are in [`templates/`](templates/).

## What the examples enforce

Each of these is a rule that lives in code rather than in a document, because a rule an agent only reads is a rule it can talk itself out of.

- **Preview by default.** Writing takes an explicit `--apply`. The preview prints the actual payload, so it doubles as the diff.
- **Read the state back.** A service call returns success when Home Assistant accepts it, not when the device does anything. `call_service.py` prints before and after, and says so when nothing moved.
- **Back up before writing, and make the rollback reversible.** `build_dashboard.py` saves the previous config first, and `restore_dashboard.py` backs up what it is replacing.
- **Validate before saving.** Home Assistant reports a broken card nowhere a person would see. `validate_dashboard.py` catches dead entities and failing templates, and exits 1.
- **Correlate replies by id, not by arrival order.** The naive version works until any subscription is open, then silently returns the wrong frame.
- **Fail with the real error.** Every failure names the exact code, message, or symptom, so the next step is obvious.
- **No credentials in code.** Everything reads a gitignored `.env`.

## License

MIT. See [LICENSE](LICENSE).

By Eric Mason ([@ericmason](https://github.com/ericmason)).
