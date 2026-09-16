# Getting connected

You need two things: your Home Assistant URL and a long-lived access token. Everything in this repository reads both from a `.env` file, so no script ever contains a credential.

## Create a long-lived access token

1. Open Home Assistant in a browser.
2. Click your user name at the bottom of the sidebar.
3. Open the **Security** tab.
4. Scroll to **Long-lived access tokens** and click **Create token**.
5. Name it something you will recognize later, such as `claude-code`.
6. Copy the token. Home Assistant shows it once and never again.

The token inherits your account's permissions. Create it on an admin account, because most configuration surfaces reject a non-admin token with a 403. If you want to limit what an agent can reach, make a separate Home Assistant user, decide what it can see, and mint the token there.

To revoke a token, return to the same screen and delete it. Revocation is immediate, which makes a token far easier to take back than a password.

## Set up your credentials

Copy the template and fill it in:

```bash
cp .env.example examples/.env
```

Then edit `examples/.env`:

```
HA_URL=http://homeassistant.local:8123
HA_TOKEN=paste-your-long-lived-token-here
```

Use whatever URL works in your browser. `http://homeassistant.local:8123` resolves through mDNS on most networks. An IP address works too. If your instance is served over HTTPS, use `https://` and the examples switch to `wss://` for you.

Confirm `.env` is ignored before you commit anything:

```bash
git check-ignore -v examples/.env
```

That prints the `.gitignore` line doing the ignoring. No output means the file is not ignored, and you are one `git add .` away from publishing your token.

Keeping credentials in `.env` rather than in the scripts is the one thing here worth copying into your own project even if you copy nothing else. A token pasted into a script gets committed, and a token in git history is a token you have to rotate.

## Install the dependency

The examples need Python 3.11 or newer and one package:

```bash
pip install -r requirements.txt
```

Everything else is standard library. REST calls go through `urllib`, so only the WebSocket examples need `websockets`.

## Run whoami first

```bash
python3 examples/whoami.py
```

You should see something like:

```
connecting to http://homeassistant.local:8123
credentials from /path/to/examples/.env

authenticated
  name       Home
  version    2026.9.2
  time zone  America/Chicago
  components 171
  entities   122
```

Run this before anything else. If it fails, every other example fails the same way, and the output here is three lines rather than a traceback.

**`HA_TOKEN is not set`**: the `.env` file is missing, or it is somewhere the loader does not look. It checks `HA_ENV_FILE`, then `examples/.env`, then `.env` at the repository root.

**`authentication failed: Invalid access token`**: the token is wrong, truncated, or was deleted. Mint a new one.

**`No route to host` or a connection timeout**: the URL is wrong or the instance is unreachable from this machine. Open the same URL in a browser on the same machine to check.

**`Name or service not known`**: `homeassistant.local` did not resolve. Use the IP address instead.

## Then take an inventory

```bash
python3 examples/inventory.py > inventory.txt
```

This prints every integration, area, device, and entity grouped by domain. Keep the output. It is the map an agent needs before it can say anything specific about your house, and having it on disk saves you from re-answering "what is that sensor called" twenty times.

Entity ids are the thing to get right. They are stable, they are what every automation and dashboard card refers to, and Home Assistant gives no useful error when one is wrong: an automation pointing at a deleted entity never fires, and a card pointing at one renders as "Entity not available". Confirm an id before you write it anywhere:

```bash
python3 examples/get_states.py --match garage
```

## Where to go next

- [websocket-vs-rest.md](websocket-vs-rest.md) tells you which API serves what, and what each wrong guess looks like.
- [safety.md](safety.md) covers the conventions that keep a write from becoming an incident.
- [working-with-an-agent.md](working-with-an-agent.md) covers pointing Claude Code at all of this.
