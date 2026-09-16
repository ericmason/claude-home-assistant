"""Connect to the Home Assistant WebSocket API and call commands on it.

This is the one module the other examples share. Everything else in this
repository is a standalone script, because a script an agent can read in one
sitting is easier to reason about than a framework. This module is the
exception, and it earns it: the authentication handshake and the request
correlation are subtle enough that copying them into twenty files means
debugging them twenty times.

Message types used here:

    auth_required, auth, auth_ok, auth_invalid  the handshake
    result                                      the reply to every command

REST endpoints used here:

    any path under /api/, through rest()

Usage:

    import asyncio
    from ha_ws import connect, call, rest

    async def main():
        async with connect() as ws:
            states = await call(ws, {"type": "get_states"})
            print(len(states))

    asyncio.run(main())
"""

import contextlib
import json
import urllib.error
import urllib.parse
import urllib.request

import websockets

from _env import HA_TOKEN, HA_URL

# A full dashboard config or a backup listing exceeds the library default of
# 1 MiB, and the connection closes with "message too big" rather than an error
# you can act on. Raise the cap once, here.
MAX_FRAME_BYTES = 32 * 1024 * 1024


def ws_url():
    """Return the WebSocket URL derived from HA_URL."""
    parts = urllib.parse.urlsplit(HA_URL)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urllib.parse.urlunsplit((scheme, parts.netloc, "/api/websocket", "", ""))


class HomeAssistantError(RuntimeError):
    """A command came back with success false."""


class Session:
    """An authenticated connection plus the command id counter it needs."""

    def __init__(self, socket):
        self.socket = socket
        self.next_id = 0

    async def send(self, payload):
        """Send one JSON frame."""
        await self.socket.send(json.dumps(payload))

    async def recv(self):
        """Receive one JSON frame."""
        return json.loads(await self.socket.recv())


@contextlib.asynccontextmanager
async def connect():
    """Open an authenticated WebSocket connection and yield a Session.

    Home Assistant sends auth_required first, then expects an auth frame, then
    replies auth_ok or auth_invalid. Command ids start at 1 and must increase
    for the rest of the connection.
    """
    async with websockets.connect(ws_url(), max_size=MAX_FRAME_BYTES) as socket:
        session = Session(socket)

        hello = await session.recv()
        if hello.get("type") != "auth_required":
            raise HomeAssistantError(f"unexpected greeting: {hello}")

        await session.send({"type": "auth", "access_token": HA_TOKEN})
        reply = await session.recv()
        if reply.get("type") != "auth_ok":
            raise HomeAssistantError(
                f"authentication failed: {reply.get('message', reply)}. "
                "Check HA_TOKEN in your .env file."
            )

        yield session


async def call(ws, message):
    """Send one command on a Session and return its result.

    Correlates the reply by id and by type == "result". Do not read the next
    frame and assume it is the answer: as soon as any subscription is open,
    event frames arrive between your request and its reply, and the naive
    version returns an event where you expected a result.

    Raises HomeAssistantError when Home Assistant reports success false, which
    is how you find out that a command name is wrong. The error code
    unknown_command means the command does not exist on the WebSocket API, and
    the surface probably lives on REST instead. See docs/websocket-vs-rest.md.
    """
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


def rest(path, data=None, method=None, timeout=30):
    """Call a REST endpoint and return the decoded JSON body.

    Pass data to send a JSON body, which implies POST unless you set method.
    Some endpoints answer with an empty body, in which case this returns None.

    Raises urllib.error.HTTPError. A 404 from a path you expected to exist
    usually means the surface is WebSocket-only rather than that you typed the
    path wrong. See docs/websocket-vs-rest.md.
    """
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(
        f"{HA_URL}{path}",
        data=body,
        method=method or ("POST" if body else "GET"),
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode()
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
