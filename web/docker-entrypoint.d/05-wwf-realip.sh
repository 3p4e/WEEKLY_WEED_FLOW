#!/bin/sh
# Trusted-proxy resolution for web/nginx.conf (review 2026-09-27, R2-BC-03).
#
# nginx's realip module takes the client address out of X-Forwarded-For only
# when the direct peer is listed in set_real_ip_from, and that directive takes
# addresses, not names. Traefik's network (traefik_network) is external to
# this stack and has no subnet the repo can pin — and pinning the subnet
# would trust every container on it, which is the hole this closes. So the
# Traefik container's own address is resolved here, through Docker's
# embedded DNS, and written as the one trusted proxy. The stock nginx image
# runs this before nginx starts (/docker-entrypoint.d), and the background
# loop at the bottom re-resolves while nginx runs, so a Traefik restart that
# hands it a new address does not silently collapse the per-client login
# bucket into one until the frontend is recreated.
#
#   WWF_TRAEFIK_HOST     name(s) to resolve, space-separated (default: traefik —
#                        the Traefik container's name/alias on traefik_network;
#                        docker-compose.yml passes ${TRAEFIK_HOST}).
#   WWF_TRAEFIK_CIDRS    explicit addresses/CIDRs to trust instead of, or as
#                        well as, the resolved ones (e.g. a fixed Traefik IP).
#   WWF_REALIP_REFRESH_S seconds between re-resolutions (default 60; 0 = once).
#
# FAIL-SAFE: an empty snippet trusts nobody. Every request then keeps
# Traefik's address as its client address — one shared bucket, loudly
# logged — never an address a sibling container chose.
set -u

SNIPPET_DIR="${WWF_REALIP_DIR:-/etc/nginx/wwf-realip.d}"
SNIPPET="$SNIPPET_DIR/traefik.conf"
HOSTS="${WWF_TRAEFIK_HOST:-traefik}"
CIDRS="${WWF_TRAEFIK_CIDRS:-}"
REFRESH="${WWF_REALIP_REFRESH_S:-60}"

log() { echo "wwf-realip: $*" >&2; }

resolve_one() {
  # Every address a name resolves to, one per line. getent first (musl-utils,
  # in the alpine base image); busybox nslookup as the fallback.
  if command -v getent >/dev/null 2>&1; then
    getent ahosts "$1" 2>/dev/null | awk '{print $1}' | sort -u
    return 0
  fi
  nslookup "$1" 2>/dev/null | awk '/^Name:/ {n=1} n && /^Address/ {print $2}' | sort -u
}

trusted() {
  # The full trusted list: explicit CIDRs, then every resolved address.
  for c in $CIDRS; do echo "$c"; done
  for h in $HOSTS; do resolve_one "$h"; done
}

write_snippet() {
  mkdir -p "$SNIPPET_DIR"
  {
    echo "# written by /docker-entrypoint.d/05-wwf-realip.sh — do not edit; see web/nginx.conf"
    printf '%s\n' "$1" | awk 'NF { print "set_real_ip_from " $1 ";" }'
  } > "$SNIPPET.tmp"
  mv -f "$SNIPPET.tmp" "$SNIPPET"
}

# One resolution pass. $1 = the list currently in the snippet; prints the
# list now in force. Rewrites the snippet (and reloads nginx, when asked to)
# only when the list changed.
pass() {
  want="$(trusted | grep -v '^$' | sort -u)"
  if [ "$want" != "$1" ]; then
    write_snippet "$want"
    if [ -z "$want" ]; then
      log "WARNING: could not resolve '$HOSTS' and WWF_TRAEFIK_CIDRS is empty — NO proxy is trusted; every client will share Traefik's address (one login-rate-limit bucket). Set TRAEFIK_HOST to the Traefik container's name on traefik_network (docs/DEPLOY.md)."
    else
      log "trusting X-Forwarded-For from: $(printf '%s' "$want" | tr '\n' ' ')"
    fi
    if [ "${2:-}" = reload ]; then
      if nginx -s reload 2>/dev/null; then
        log "reloaded nginx with the new trusted-proxy list"
      else
        log "WARNING: nginx reload failed; the new list applies at the next restart"
      fi
    fi
  fi
  printf '%s' "$want"
}

current="$(pass "__unset__")"

case "$REFRESH" in
  ''|0|*[!0-9]*) exit 0 ;;
esac
# Re-resolve in the background for the life of the container; the
# entrypoint returns so nginx can start.
(
  while sleep "$REFRESH"; do
    current="$(pass "$current" reload)"
  done
) &
exit 0
