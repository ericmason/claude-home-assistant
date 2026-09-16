# WebSocket or REST: which API does what

Home Assistant has two APIs that overlap almost everywhere and diverge in a handful of places. Neither one documents its own gaps, so you find the boundary by hitting it. This page is that boundary written down.

The short version: use the WebSocket API for everything, and drop to REST for the five or six surfaces that have no WebSocket command. When you pick wrong you get a 404 or an `unknown_command`, both of which read like you typed something wrong rather than like you used the wrong API.

## The decision table

| What you want to do | Use | Command or endpoint | What the wrong choice gives you |
| --- | --- | --- | --- |
| Read every entity state | either | `get_states` or `GET /api/states` | both work |
| Call a service | either | `call_service` or `POST /api/services/{domain}/{service}` | both work |
| Create an input helper | WebSocket | `input_boolean/create`, `input_number/create`, `input_datetime/create` | REST `POST /api/config/input_boolean/config/<id>` returns 404 with the body `404: Not Found` |
| Read or write the entity registry | WebSocket | `config/entity_registry/get`, `/update`, `/list` | there is no REST route; you get 404 |
| Read or write the device or area registry | WebSocket | `config/device_registry/list`, `config/area_registry/list` | there is no REST route; you get 404 |
| Save a dashboard | WebSocket | `lovelace/config/save` | there is no REST route; editing `.storage` by hand needs a restart |
| Create a dashboard | WebSocket | `lovelace/dashboards/create` | there is no REST route |
| Read automation traces | WebSocket | `trace/list`, `trace/get` | there is no REST route |
| List repair issues | WebSocket | `repairs/list_issues` | there is no REST route |
| Reach the Supervisor | WebSocket | `supervisor/api` with `endpoint` and `method` | `unknown_command` on installs with no Supervisor |
| Take a backup | WebSocket | `backup/generate`, `backup/info` | there is no REST route |
| Expose entities to a voice assistant | WebSocket | `homeassistant/expose_entity`, `cloud/alexa/entities` | there is no REST route |
| **Create an automation** | **REST** | `POST /api/config/automation/config/{id}` | WebSocket `automation/config` reads only; there is no create command |
| **Create a script** | **REST** | `POST /api/config/script/config/{id}` | same |
| **Create a scene** | **REST** | `POST /api/config/scene/config/{id}` | same |
| **Delete a config entry** | **REST** | `DELETE /api/config/config_entries/entry/{id}` | WebSocket `config_entries/delete` returns `unknown_command` |
| **Start a template sensor** | **REST** | `POST /api/config/config_entries/flow` with `handler: "template"` | one POST starts a multi-step flow and returns a `flow_id`; it does not create the sensor. Post each step back to `/api/config/config_entries/flow/{flow_id}` |
| **Render a template** | **REST** | `POST /api/template` | WebSocket `render_template` subscribes: its result is `null` and the value arrives in a later event frame |
| Read history | either | `GET /api/history/period/{start}` or `history/history_during_period` | both work for a one-shot read. `history/stream` is the streaming one, so do not reach for it when you want a single answer |
| **Read an add-on log** | **REST** | `GET /api/hassio/addons/{slug}/logs` | returns plain text, not JSON |

The rule behind the table: the WebSocket API owns anything that is *live state* or *registry*, and REST owns anything that is *a config file on disk*. Automations, scripts, and scenes are files. Entities, areas, and dashboards are state.

## Reading the errors

`unknown_command` on the WebSocket API means that command name does not exist in this Home Assistant version. Check the spelling, then check whether the surface is REST-only in the table above. It never means your token is wrong.

A 404 from REST means the same thing in the other direction: that route does not exist. Home Assistant returns 404 for routes it does not serve and for entities that do not exist, so a 404 from `/api/states/light.typo` and a 404 from `/api/config/input_boolean/config/x` look identical and mean different things.

A 401 means the token is wrong or expired. A 403 means the token is fine but the user is not an admin. Most config surfaces need an admin token.

`config_not_found` from `lovelace/config` means nobody has ever edited that dashboard, so it has no stored config and Home Assistant is generating its views on every load. It is not an error, and there is nothing to validate.

## The authentication handshake

The WebSocket handshake is fixed and every connection does it:

1. Connect to `ws://your-host:8123/api/websocket`, or `wss://` when the instance is served over HTTPS.
2. Home Assistant sends `{"type": "auth_required", "ha_version": "..."}`.
3. You send `{"type": "auth", "access_token": "..."}`.
4. Home Assistant replies `{"type": "auth_ok"}` or `{"type": "auth_invalid", "message": "..."}`.

Only after `auth_ok` can you send commands. Command ids start at 1 and must increase for the life of the connection. Reusing an id gets you `id_reuse`.

`examples/ha_ws.py` does all of this in `connect()`.

## Correlate replies by id, never by arrival order

This is the bug that takes longest to find, because the naive version works until it does not.

Most example code sends a command and then reads the next frame, assuming it is the answer. That holds only while nothing else is talking. The moment any subscription is open, whether you opened it or a shared helper did, event frames arrive between your request and its reply, and your code returns an event where it expected a result.

Match on both the id and the type:

```python
async def call(ws, message):
    ws.next_id += 1
    message_id = ws.next_id
    await ws.send({**message, "id": message_id})

    while True:
        frame = await ws.recv()
        if frame.get("id") != message_id or frame.get("type") != "result":
            continue
        if not frame.get("success"):
            error = frame.get("error", {})
            raise HomeAssistantError(
                f"{message.get('type')} failed: "
                f"{error.get('code', 'unknown')}: {error.get('message', frame)}"
            )
        return frame.get("result")
```

That is `call()` from `examples/ha_ws.py`. Checking `success` matters as much as the correlation: a failed command still comes back as a `result` frame, so code that skips the check hands you an error frame and calls it data.

The symptom when you get the correlation wrong is a `KeyError` on `result`, or a function that returns another command's data. Both look like a Home Assistant bug and are not.

## Raise the frame size limit

The `websockets` library defaults to a 1 MiB maximum frame. Two responses routinely exceed it:

- a full dashboard config, especially one with many views
- `backup/info` on an instance with a long backup history

When a frame is too big the connection closes with `message too big` rather than returning an error you can catch, so it reads like a network problem. Set `max_size` when you connect:

```python
websockets.connect(url, max_size=32 * 1024 * 1024)
```

`examples/ha_ws.py` sets this once, which is one of the reasons it exists.

## Check the success field

Every WebSocket reply carries `success`. A reply with `"success": false` has an `error` object with a `code` and a `message`, and that message is usually specific enough to act on. Code that reads `result` without checking `success` fails later, somewhere unrelated, with a confusing traceback.

REST is the same idea with status codes. `urllib` raises `HTTPError` on 4xx and 5xx, and the response body holds the real message. Read it:

```python
except urllib.error.HTTPError as error:
    detail = error.read().decode(errors="replace")
```

A bad Jinja template answers 400 with the Jinja error and a line number in the body. The status line alone tells you nothing.

## Success is not the same as it worked

`call_service` returns success as soon as Home Assistant accepts the call, not when anything happens. A light that is unplugged, a Z-Wave device that never woke up, and a cloud integration that timed out all return success.

Read the entity state back afterwards. `examples/call_service.py` does, and prints the before and after so the difference between "accepted" and "worked" is visible. See [safety.md](safety.md).
