#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage: ./scripts/install.sh [--offline] [--force] [--embeddings] [--local-models]' \
    '' \
    'Installs the current trusted checkout with uv.' \
    '--embeddings installs local encoder dependencies; model weights remain separately provisioned.' \
    '--local-models also installs both sensitivity dependencies and packaged NudeNet weights; NSFW weights must already be local.' \
    'The script never installs uv, system packages, model weights, or Agent configuration.'
}

offline=false
force=false
embeddings=false
local_models=false
while (($#)); do
  case "$1" in
    --offline)
      offline=true
      ;;
    --force)
      force=true
      ;;
    --embeddings)
      embeddings=true
      ;;
    --local-models)
      local_models=true
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
if [[ "$local_models" == true ]]; then
  arguments+=("$project_root[local-models]")
elif [[ "$embeddings" == true ]]; then
  arguments+=("$project_root[embeddings]")
else
  arguments+=("$project_root")
fi

exec uv "${arguments[@]}"
