#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
STAGE="${ROOT}/build/deb-stage"
OUT="${ROOT}/dist"
APP="${STAGE}/opt/ghostwriter"

rm -rf "${ROOT}/build"
mkdir -p "${STAGE}/DEBIAN" "${APP}" "${OUT}"

cp "${ROOT}/packaging/deb/DEBIAN/control" "${STAGE}/DEBIAN/control"
cp "${ROOT}/packaging/deb/DEBIAN/postinst" "${STAGE}/DEBIAN/postinst"
cp "${ROOT}/packaging/deb/DEBIAN/prerm" "${STAGE}/DEBIAN/prerm"
chmod 0755 "${STAGE}/DEBIAN/postinst" "${STAGE}/DEBIAN/prerm"
sed -i "s/__VERSION__/${VERSION}/g" "${STAGE}/DEBIAN/control"

# Nur benötigte Quellen (kein .venv, kein build-in-build)
cp -a "${ROOT}/ghostwriter" "${APP}/"
cp -a "${ROOT}/packaging" "${APP}/"
cp -a "${ROOT}/pyproject.toml" "${APP}/"
cp -a "${ROOT}/README.md" "${APP}/"
cp -a "${ROOT}/VERSION" "${APP}/"
cp -a "${ROOT}/scripts" "${APP}/"
# Tests optional für Nachvollziehbarkeit
cp -a "${ROOT}/tests" "${APP}/"
cp -a "${ROOT}/.pre-commit-config.yaml" "${APP}/" 2>/dev/null || true

# Bytecode entfernen
find "${APP}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

dpkg-deb --build "${STAGE}" "${OUT}/GhostWriter-${VERSION}-amd64.deb"
echo "Built ${OUT}/GhostWriter-${VERSION}-amd64.deb"
