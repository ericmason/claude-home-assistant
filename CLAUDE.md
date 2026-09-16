# Rules for this repository

This is a teaching repository. The examples in `examples/` are meant to be read as much as run, so a change that makes one shorter and clearer is usually right, and a change that makes one more general is usually wrong.

Looking for a template to copy into your own Home Assistant project? Use `templates/CLAUDE.md`, not this file. This one is about working on this repository.

## Run whoami first

```bash
python3 examples/whoami.py
```

If it fails, every other example fails the same way. Fix it here, where the output is three lines rather than a traceback.

## Credentials come from .env, never from a script

Every example imports `HA_URL` and `HA_TOKEN` from `examples/_env.py`, which reads `examples/.env`. No script in this repository contains a token, and none ever should.

`examples/.env` is gitignored. Before committing, confirm it still is:

```bash
git check-ignore -v examples/.env
```

Never commit a `.env`, a token, an IP address from a real network, or a dashboard backup. Backups under `examples/dashboards/backups/` are a full inventory of whoever ran the builder, which is why `backups/` is ignored.

## Writes preview by default

Every example that changes anything prints the exact payload it would send and exits. Writing requires `--apply`.

Keep this when you add an example. The preview is the diff: it shows the real payload, not a summary. An agent can run the preview freely while reasoning, and the human adds the flag.

## Conventions for a new example

- **One script per task**, named `verb_noun.py`, so the filename says what it does.
- **A module docstring** stating what the script does, the message types or endpoints it uses, and a usage line or two.
- **`argparse`**, not `sys.argv` indexing.
- **Import `_env` and `ha_ws`.** Do not re-implement the handshake, the id correlation, or the `max_size` setting.
- **Read state back after a write.** A response code is a claim about Home Assistant's inbox, not about the house.
- **Every gotcha in a comment names the exact error or symptom**, not "this can fail."

Add the script to `examples/README.md` in the same change.

## Writing style

Google developer documentation style: second person, active voice, present tense, sentence-case headings, condition before instruction. American English. No em dashes. One line per paragraph in Markdown, never hard-wrapped.

Docs are for a stranger who runs Home Assistant and has never seen this repository. Assume no context.

## Verify against a real instance

Do not claim an example works without running it. A throwaway instance in Docker is enough and risks nothing:

```bash
docker run -d --name ha-test -p 8124:8123 ghcr.io/home-assistant/home-assistant:stable
```

Onboard it through `POST /api/onboarding/users`, add `demo:` to its `configuration.yaml` for a few hundred entities to work with, and point `HA_ENV_FILE` at a `.env` holding its URL and token.

Never run a write example with `--apply` against an instance that runs a real house.
