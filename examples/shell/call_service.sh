#!/bin/sh
# Turn a switch on for N minutes, then put it back the way you found it.
#
# A worked example of the safety rule that matters most in shell: if your script
# changes something, it restores it on every exit path, including Ctrl-C and a
# kill. A script that leaves a valve open because you interrupted it is worse
# than no script.
#
# Usage:
#   HA_TOKEN=<long-lived token> ./call_service.sh <minutes> <entity_id> [entity_id ...]
#
# Example:
#   HA_TOKEN=... ./call_service.sh 5 switch.garden_hose switch.patio_lights
#
# Set HA_URL to point somewhere other than the default. Run this from inside an
# add-on and the API answers at http://homeassistant:8123, which is the name the
# core container has on the internal Docker network. Do not use localhost there,
# because inside an add-on container localhost is the add-on.
#
# Exit codes: 0 fine, 2 no token, 64 bad arguments.
#
# Needs curl and jq.

set -eu

API="${HA_URL:-http://homeassistant.local:8123}/api"

if [ -z "${HA_TOKEN:-}" ]; then
  echo "set HA_TOKEN to a Home Assistant long-lived access token" >&2
  exit 2
fi
TOKEN="$HA_TOKEN"

[ $# -ge 2 ] || {
  echo "usage: $0 <minutes> <entity_id> [entity_id ...]" >&2
  exit 64
}

MINUTES="$1"
shift
ENTITIES="$*"

case "$MINUTES" in
  ''|*[!0-9]*) echo "minutes must be a whole number, got: $MINUTES" >&2; exit 64 ;;
esac

log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }

api() { # api <METHOD> <path> [json body]
  if [ $# -ge 3 ]; then
    curl -sf -m 30 -X "$1" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$3" "$API/$2"
  else
    curl -sf -m 30 -X "$1" -H "Authorization: Bearer $TOKEN" "$API/$2"
  fi
}

state_of() { # state_of <entity_id>; prints the state, fails when the read fails
  # Capture the body first. Piping curl straight into jq throws away curl's exit
  # status, because a pipeline reports jq's, so a 404 for a typo'd entity id
  # would look like a successful read of an empty state.
  body="$(api GET "states/$1")" || return 1
  printf '%s' "$body" | jq -er '.state'
}

original_state() { # original_state <entity_id>; prints what it was before
  for pair in $ORIGINAL; do
    case "$pair" in
      "$1="*) printf '%s' "${pair#*=}"; return 0 ;;
    esac
  done
  return 1
}

switch_to() { # switch_to turn_on|turn_off <entity_id>
  api POST "services/switch/$1" "{\"entity_id\":\"$2\"}" > /dev/null
}

# Record what every entity looked like before you touched it, so the cleanup
# knows what "back the way you found it" means.
ORIGINAL=""
for entity in $ENTITIES; do
  if ! before="$(state_of "$entity")"; then
    echo "cannot read $entity; check the entity id" >&2
    exit 64
  fi
  log "$entity is $before"
  ORIGINAL="$ORIGINAL $entity=$before"
done

RUNNING=""
SLEEP_PID=""

cleanup() {
  status=$?
  [ -z "$SLEEP_PID" ] || kill "$SLEEP_PID" 2>/dev/null || true
  [ -z "$RUNNING" ] || {
    switch_to turn_off "$RUNNING" || true
    log "$RUNNING off"
  }
  # Put back anything that was on before you started.
  for pair in $ORIGINAL; do
    entity="${pair%%=*}"
    was="${pair#*=}"
    if [ "$was" = "on" ]; then
      switch_to turn_on "$entity" || true
      log "$entity restored to on"
    fi
  done
  exit "$status"
}

# EXIT alone is not enough: a shell killed by a signal runs the INT and TERM
# traps, and without them the cleanup never happens.
trap cleanup EXIT INT TERM

log "running each of$ORIGINAL for $MINUTES minute(s)"

for entity in $ENTITIES; do
  log "$entity on for $MINUTES min"
  RUNNING="$entity"
  switch_to turn_on "$entity"

  # Backgrounded so a TERM interrupts the wait instead of queuing behind it.
  sleep $((MINUTES * 60)) &
  SLEEP_PID=$!
  wait "$SLEEP_PID" || true
  SLEEP_PID=""

  RUNNING=""
  # An entity that was already on stays on. Turning it off here would leave it
  # off for the rest of a multi-entity run, and only the exit trap would put it
  # back, long after the window it belonged to has passed.
  if [ "$(original_state "$entity")" = "on" ]; then
    log "$entity was already on before this run, leaving it on"
  else
    switch_to turn_off "$entity"
    log "$entity off, now $(state_of "$entity" || echo unreadable)"
  fi
done

log "done"
