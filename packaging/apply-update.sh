#!/bin/bash
# Installiert ein GhostWriter-*.deb.
# Aufruf: pkexec /usr/lib/ghostwriter/apply-update.sh /pfad/zum.deb
set -euo pipefail
DEB="${1:-}"
if [[ -z "$DEB" || ! -f "$DEB" ]]; then
  echo "Usage: $0 /path/to/GhostWriter-VERSION-amd64.deb" >&2
  exit 2
fi
case "$(basename "$DEB")" in
  GhostWriter-*.deb|ghostwriter-*.deb) ;;
  *)
    echo "Nur GhostWriter-*.deb erlaubt." >&2
    exit 2
    ;;
esac
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get install -y --reinstall "$DEB" || dpkg -i "$DEB"
else
  dpkg -i "$DEB"
fi
echo "GhostWriter-Update installiert."
