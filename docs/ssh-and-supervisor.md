# SSH and the Supervisor

Most of what you need is reachable over the API. A few things are not: reading `/config/.storage`, restarting the core, checking that a YAML change parses, and deploying a custom integration. Those need a shell on the host.

This page assumes Home Assistant OS or Supervised. On Container or Core you already have a shell, and the `ha` command does not exist.

## Get a shell

Install the **Advanced SSH & Web Terminal** add-on, or the official **Terminal & SSH** add-on. In its configuration, add your public key and set the port. The add-on's own terminal in the sidebar works too and needs no key at all.

```bash
ssh -i ~/.ssh/id_ed25519 root@homeassistant.local
```

Use a key, not a password. The add-on accepts passwords and people set weak ones, and this is a shell on the machine that controls your locks.

## The ha command

```bash
ha core check      # does the configuration parse
ha core restart    # restart Home Assistant, not the host
ha core logs       # the core log
ha core logs -f    # follow it
ha core info       # version and install details
ha supervisor logs # the Supervisor's own log
ha addons          # list add-ons
```

**Run `ha core check` before every restart.** It parses the configuration and reports the error with a file and a line. Restarting on a broken config gives you an instance that does not come back, and then you are debugging YAML through a recovery console instead of through a terminal.

Restarting the core takes a minute or two on modest hardware. Traces survive it: a clean stop saves them to `.storage/trace.saved_traces` and startup restores them. Pulling the power does not save them.

## Reading /config/.storage

This is where dashboards, config entries, the entity registry, and user data actually live.

```bash
ls /config/.storage/ | grep lovelace
cat /config/.storage/core.config_entries | head -50
```

**Use `ls | grep`, not a glob.** `lovelace.dashboard_*` misses `lovelace.lovelace`, which is the default dashboard, so a hand-built dashboard looks auto-generated and you skip backing it up.

Reading these is fine and often the fastest way to see what is stored, including the configuration an integration is using. **Writing them is not.** Home Assistant caches all of it in memory and rewrites the files from that cache, so a hand edit is invisible until a restart and can be discarded outright. Use the API. See [safety.md](safety.md).

Be aware of what is in there. `core.config_entries` holds integration credentials in plain text: API keys, device passwords, cloud tokens. Do not paste it into anything, and do not hand the whole file to an agent when you meant to ask about one integration.

## From inside an add-on, the API is not on localhost

This one costs an hour the first time.

Inside an add-on container, `localhost` is the add-on, not Home Assistant. A script that works on your laptop against `http://homeassistant.local:8123` and then fails with connection refused after you copy it to the host is hitting this.

From inside an add-on, Home Assistant answers at:

```
http://homeassistant:8123
```

That hostname resolves on the internal Docker network. `examples/shell/call_service.sh` documents it at the top for the same reason.

## Long jobs: use setsid

A command you start over SSH dies when the connection drops, and the connection drops when your laptop sleeps. Anything that runs for more than a few minutes needs to survive that:

```bash
setsid sh -c './long_running_job.sh > /tmp/job.log 2>&1' &
tail -f /tmp/job.log
```

`setsid` detaches the process from the terminal, so closing the session leaves it running. Then follow the log separately. `nohup` works too.

This matters most for an agent, whose session can end for reasons unrelated to the job. A half-run irrigation script that stopped when a laptop lid closed leaves a valve open.

## Deploying a custom integration

Copy the directory and confirm what landed:

```bash
scp -r custom_components/my_integration root@homeassistant.local:/config/custom_components/
ssh root@homeassistant.local 'cd /config/custom_components/my_integration && md5sum *.py'
md5sum custom_components/my_integration/*.py
```

**Compare the checksums.** `scp` succeeding means bytes moved, not that the right bytes moved to the right place. A copy into a path that already had an older directory, or a partial transfer, both look like success. Comparing md5sums takes one command and is the difference between debugging your code and debugging your deploy.

Then restart:

```bash
ha core restart
```

**Restart, not reload.** Python modules are imported once per process, so a code change needs a new process. Reloading the integration re-runs setup with the old code still in memory, which produces the confusing result of a deploy that clearly worked and behavior that clearly did not change. See [custom-integrations.md](custom-integrations.md).

## The Supervisor API without SSH

Most of the Supervisor is reachable over the WebSocket API, so you do not need a shell for a quick look:

```python
{"type": "supervisor/api", "endpoint": "/addons", "method": "get"}
```

`examples/addon_logs.py` uses this to list add-ons and then reads one's log through `GET /api/hassio/addons/{slug}/logs`. On an install with no Supervisor the command answers `unknown_command`, which is how the example tells you which install type you have.
