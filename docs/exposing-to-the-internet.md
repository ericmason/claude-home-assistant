# Exposing part of Home Assistant to the internet

Sooner or later you want to hand someone a page: a contractor who needs to run a valve from the yard, a house sitter who needs one light, a family member who needs one button. Giving them a Home Assistant login is more access than the job needs, and setting up a restricted user for a two-hour visit is more work than the job deserves.

So you build a small page. This is where an agent will cheerfully build you something that works and is a standing liability, because "it works" and "it is safe to leave running" look identical from the outside.

## The same feature, built twice

Both versions serve the same page and do the same thing. They differ entirely in what happens after you stop paying attention.

### Version A: an edge worker at a secret URL

A small serverless function deployed at a random path. It holds a long-lived Home Assistant token and proxies the few calls the page needs.

It works on the first try, it is fast, and it needs no changes inside Home Assistant.

What it actually is:

- **A standing credential.** The token is long-lived, so it works for years, and it is full-access: the page only calls two services, but the token can call every one.
- **No off switch.** To revoke access you redeploy the worker or revoke the token, which means opening a laptop. There is nothing to toggle from your phone.
- **No expiry.** The page works forever. Nobody remembers to take it down after the contractor leaves.
- **Security by URL only.** Anyone who gets the link has it permanently. Links leak through screenshots, group chats, and browser history on a shared phone.
- **A second secret to rotate**, in a system separate from Home Assistant, with its own deploy step you will forget.

The failure mode is not dramatic. It is that eighteen months later there is a URL you have forgotten about, holding a token you have forgotten about, that still controls your house.

### Version B: a custom integration gated by a switch

The same page, served by Home Assistant itself, through a `HomeAssistantView`. See [custom-integrations.md](custom-integrations.md).

- **No token anywhere.** The page runs inside Home Assistant and calls services directly. There is no credential to leak, because there is no credential.
- **An off switch on your phone.** Every route checks a switch entity. Off means the routes return 404. Revoking access is one toggle, from wherever you are, with no redeploy.
- **It turns itself off.** Turning the switch on starts a four-hour window. You cannot forget to close it, because it closes itself.
- **The expiry survives a restart.** The switch stores `expires_at` and re-checks it on startup, so a restart during the window does not silently extend access forever.
- **Key rotation is a button.** Turning the switch on mints a fresh key, so every hand-out gets a new URL and yesterday's link is already dead.
- **One place to audit.** The switch is an entity, so its history shows every time access was opened and closed.

Version B is more work to build. It is the one to leave running.

## The principle

**An access mechanism needs an off switch that reaches the person who owns it.** Not "we could revoke the token", not "we could redeploy". It has to be a control that the owner can reach from their phone, in seconds, without tools.

Add to that: **access should default to closed and get there on its own.** Anything requiring a human to remember to revoke it will eventually not be revoked. This is why the auto-off matters more than it looks. It converts "I must remember to close this" into "this closes itself and I can reopen it."

A secret URL is a real layer and not a sufficient one. Use it alongside a gate, never instead of one.

## Review checklist

Before you expose anything, and especially before you accept something an agent wrote:

**Authorization**

- [ ] Every route checks the gate, including static assets and the event stream.
- [ ] Authorization is re-checked after any `await` that yields. A handler that checks the gate, awaits, then acts has a window where the switch closed in between. For a long-lived stream, that window is the life of the stream.
- [ ] Closing the gate cancels open streams. A guest with the page already loaded should lose it, not keep a working connection.
- [ ] The scope is the minimum: the specific entities, the specific services. Not a general proxy.

**Resource limits**

- [ ] Event queues are bounded. An unbounded queue feeding a client that stopped reading grows until Home Assistant runs out of memory. Cap it and drop the oldest.
- [ ] Every write has a timeout. A client that opens a connection and never reads holds a writer forever.
- [ ] Streams are canceled on entry unload, so a reload does not leak them.
- [ ] Actions are rate-limited or capped. A page with a Run button needs a maximum run length enforced server side, not in the HTML.

**Information disclosure**

- [ ] Errors return a fixed string to the guest and log the real exception server side. A stack trace in a response tells a stranger your integration names, paths, and versions.
- [ ] A closed gate returns a plain 404, not a 403. A 403 confirms something is there.
- [ ] Responses set `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`. A secret URL that reaches a crawler or a shared cache is not secret.
- [ ] The page exposes only what the job needs. Not the full entity list, not the instance name, not the version.

**Lifecycle**

- [ ] Access expires on its own.
- [ ] The expiry survives a restart.
- [ ] Rotating the key invalidates the old URL immediately.
- [ ] Opening and closing access is visible in the entity's history.

## Telling an agent this

An agent optimizes for the thing you asked for, and "build me a page the contractor can use" does not contain the word revoke. It will produce Version A, because Version A is shorter, and it will be right that Version A works.

Put the requirement in the ask:

> Serve it from a custom integration, not an external service. Every route checks `switch.guest_access`, and returns 404 when it is off. Turning the switch on mints a new key and starts a four-hour auto-off whose expiry survives a restart. No long-lived token anywhere.

And put it in your `CLAUDE.md`, so you do not have to remember to say it next time. See [working-with-an-agent.md](working-with-an-agent.md).
