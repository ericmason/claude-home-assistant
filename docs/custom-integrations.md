# Writing a custom integration

At some point a script stops being the right shape. A script runs when you run it; an integration is always there, holds state across restarts, and can serve a web page. When you want something with a switch you can toggle from your phone, you want an integration.

This is a minimal but complete one: a config flow with no fields, a switch that turns itself off after a while and survives a restart, and one HTTP route.

Everything lives in `/config/custom_components/<domain>/`, where the directory name is the domain and must match the `domain` in `manifest.json`.

## manifest.json

```json
{
  "domain": "my_integration",
  "name": "My Integration",
  "codeowners": ["@you"],
  "config_flow": true,
  "dependencies": ["http"],
  "documentation": "https://github.com/you/my_integration",
  "iot_class": "local_push",
  "requirements": [],
  "version": "1.0.0"
}
```

`version` is required for a custom integration and Home Assistant refuses to load one without it. List `http` in `dependencies` if you register a view, so that the HTTP component is up before your setup runs.

## config_flow.py

A config flow with no fields is still worth having: it gives you an entry in the UI, a place to store data, and an entry id to key state off.

```python
"""Config flow for My Integration. One instance, no fields, one confirm step."""

from __future__ import annotations

import secrets
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_KEY, DOMAIN


class MyIntegrationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set the integration up, minting a secret as it goes."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm, then create the entry."""
        if user_input is None:
            return self.async_show_form(step_id="user")

        # Only one instance makes sense for this integration.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="My Integration",
            data={CONF_KEY: secrets.token_hex(12)},
        )
```

## __init__.py

Setup and unload, plus the one lifecycle fact that is not obvious.

```python
"""My Integration: set up entities and register the HTTP routes."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_ENTRY_ID, DATA_VIEWS_REGISTERED, DOMAIN
from .http import async_register_views

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set the entry up and register the HTTP routes once."""
    data = hass.data.setdefault(DOMAIN, {})
    data[DATA_ENTRY_ID] = entry.entry_id

    # Views cannot be unregistered, so register them on the first setup only.
    # They look the entry up through hass.data, so a reload keeps working.
    if not data.get(DATA_VIEWS_REGISTERED):
        async_register_views(hass)
        data[DATA_VIEWS_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the platforms. The HTTP views stay registered and go 404."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(DATA_ENTRY_ID, None)
    return unloaded
```

**Register views once per Home Assistant run, not once per setup.** Home Assistant has no API to unregister an HTTP view. Registering in `async_setup_entry` without a guard means a reload registers a second copy of every route, and the routes then close over a config entry that no longer exists. The fix is the `DATA_VIEWS_REGISTERED` flag above, plus having the view look the entry up through `hass.data` at request time rather than capturing it at registration time.

## switch.py

A switch with a timed auto-off whose expiry survives a restart. `RestoreEntity` is what makes that possible: it gives you the entity's last state and attributes when it comes back.

```python
"""A switch that turns itself off after a window, and remembers when."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

ACCESS_WINDOW = timedelta(hours=4)
ATTR_EXPIRES_AT = "expires_at"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the switch."""
    async_add_entities([MyAccessSwitch(entry)])


class MyAccessSwitch(SwitchEntity, RestoreEntity):
    """Off by default. Survives a restart as whatever it was, expiry included."""

    _attr_name = "My access"
    _attr_icon = "mdi:account-key"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_access"
        self._attr_is_on = False
        self._expires_at: datetime | None = None
        self._cancel_timer = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose when access turns itself off, so a restart can restore it."""
        return {
            ATTR_EXPIRES_AT: self._expires_at.isoformat() if self._expires_at else None
        }

    async def async_added_to_hass(self) -> None:
        """Restore the previous state, honoring an expiry that already passed."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            expires = dt_util.parse_datetime(
                last.attributes.get(ATTR_EXPIRES_AT) or ""
            )
            # An expiry in the past means the window closed while we were down.
            # Without this check, a restart silently extends access forever.
            if expires is None or expires <= dt_util.utcnow():
                self._attr_is_on = False
            else:
                self._attr_is_on = True
                self._schedule_off(expires)

    async def async_will_remove_from_hass(self) -> None:
        """Drop the timer with the entity."""
        self._cancel()

    def _cancel(self) -> None:
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    def _schedule_off(self, expires: datetime) -> None:
        self._cancel()
        self._expires_at = expires
        delay = max((expires - dt_util.utcnow()).total_seconds(), 0)
        self._cancel_timer = async_call_later(self.hass, delay, self._expire)

    @callback
    def _expire(self, _now: datetime) -> None:
        self._cancel_timer = None
        self._expires_at = None
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self._schedule_off(dt_util.utcnow() + ACCESS_WINDOW)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._cancel()
        self._expires_at = None
        self._attr_is_on = False
        self.async_write_ha_state()
```

The `expires_at` attribute is the whole trick. A timer scheduled with `async_call_later` dies with the process, so without persisting the deadline, a restart during the window leaves the switch on with nothing left to turn it off. Storing the absolute time and re-checking it on startup handles both cases: the window that is still open, and the one that closed while you were down.

## http.py

```python
"""An HTTP route that is gated by the switch."""

from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN


class MyStatusView(HomeAssistantView):
    """A small JSON status endpoint."""

    url = "/api/my_integration/status"
    name = "api:my_integration:status"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return status, or 404 when access is closed."""
        # KEY_HASS is the typed aiohttp AppKey. The bare string "hass"
        # still resolves, but it is the deprecated spelling.
        hass: HomeAssistant = request.app[KEY_HASS]

        if not self._allowed(hass):
            # A plain 404 tells a stranger nothing about what lives here.
            return web.Response(status=404)

        return web.json_response(
            {"ok": True},
            headers={
                "Cache-Control": "no-store",
                "X-Robots-Tag": "noindex, nofollow",
            },
        )

    @staticmethod
    def _allowed(hass: HomeAssistant) -> bool:
        """Check the gate. Call this again after any await that yields."""
        state = hass.states.get("switch.my_access")
        return state is not None and state.state == "on"


def async_register_views(hass: HomeAssistant) -> None:
    """Register every view. Called once per Home Assistant run."""
    hass.http.register_view(MyStatusView())
```

**Re-check authorization after any `await` that yields.** A handler that checks the gate, awaits something, and then acts has a window where the switch was turned off between the check and the action. For a single fast response that window is small; for a long-lived stream it is the whole life of the stream. Check at the top, and check again after each yield.

## Deploy it

```bash
scp -r custom_components/my_integration root@homeassistant.local:/config/custom_components/
ssh root@homeassistant.local 'cd /config/custom_components/my_integration && md5sum *.py'
md5sum custom_components/my_integration/*.py
ssh root@homeassistant.local 'ha core restart'
```

Compare the checksums. `scp` reporting success means bytes moved, not that the right bytes are in the right place.

**Restart, do not reload.** Python imports a module once per process. Reloading the integration re-runs setup with the old code still in memory, so your change has no effect and everything about the deploy looks fine. This is the single most confusing thing about custom integration development, and it applies to any file the module imports, including an HTML page you embedded as a string.

Then confirm it came back:

```bash
ssh root@homeassistant.local 'ha core logs | grep -i my_integration'
```

## Common mistakes

- **No `version` in `manifest.json`.** The integration does not load and the log says so, once, at startup.
- **Directory name does not match `domain`.** Same result.
- **Blocking I/O in the event loop.** `requests.get()` or `open()` in a coroutine stalls all of Home Assistant. Use `hass.async_add_executor_job()` or an async library. Recent versions log a warning naming your integration.
- **Capturing the config entry at view-registration time.** It is stale after a reload. Look it up through `hass.data` inside the handler.
- **Assuming a reload picks up a code change.** It does not. Restart.
