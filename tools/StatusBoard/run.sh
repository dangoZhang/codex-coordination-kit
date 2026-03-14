#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COORD_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export CODEX_COORDINATION_ROOT="${COORD_ROOT}"

swift build --package-path "${SCRIPT_DIR}" >/dev/null
exec "${SCRIPT_DIR}/.build/debug/CoordinationStatusBoard" "$@"
