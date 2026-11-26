#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $# == 0 ]]
export QA_WORK=$(mktemp -d /tmp/qa-run.XXXXXXXX)
export HOME="$QA_WORK/home" TMPDIR="$QA_WORK/tmp" XDG_CACHE_HOME="$QA_WORK/cache" PYTHONNOUSERSITE=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HOME" "$TMPDIR" "$XDG_CACHE_HOME"
cd "$(dirname "$0")"
exec timeout --kill-after=5s 2100s python3 bootstrap.py
