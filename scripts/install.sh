#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage: ./scripts/install.sh [--offline] [--force]' \
    '' \
    'Installs the current trusted checkout with uv.' \
    'The script never installs uv, system packages, optional models, or Agent configuration.'
}

offline=false
force=false
while (($#)); do
  case "$1" in
    --offline)
      offline=true
      ;;
    --force)
      force=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' \
    'MediaSense installation requires uv.' \
    'Install uv through a trusted channel, then run this script again.' >&2
  exit 1
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
project_root="$(dirname -- "$script_dir")"
arguments=(tool install)
if [[ "$offline" == true ]]; then
  arguments+=(--offline)
else
  printf '%s\n' 'uv may download the Python dependencies declared by MediaSense.'
fi
if [[ "$force" == true ]]; then
  arguments+=(--force)
fi
arguments+=("$project_root")

exec uv "${arguments[@]}"
