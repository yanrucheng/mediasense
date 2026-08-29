#!/bin/zsh
set -euo pipefail

probe_root="$(rtk mktemp -d /private/tmp/mediasense-apply-crossfs.XXXXXX)"
source_root="$probe_root/source"
mount_point="$probe_root/mounted"
image_path="$probe_root/probe.dmg"
attached=0

cleanup() {
  if (( attached )); then
    rtk hdiutil detach "$mount_point"
  fi
  rtk rm -f "$image_path"
  rtk rmdir "$mount_point" "$source_root" "$probe_root"
}
trap cleanup EXIT

rtk mkdir "$source_root" "$mount_point"
rtk hdiutil create -size 64m -fs APFS -volname MediaSenseApplyProbe \
  -ov "$image_path"
rtk hdiutil attach -nobrowse -mountpoint "$mount_point" "$image_path"
attached=1

rtk env \
  MEDIASENSE_APPLY_CROSSFS_SOURCE_ROOT="$source_root" \
  MEDIASENSE_APPLY_CROSSFS_TARGET_ROOT="$mount_point" \
  uv run pytest -q -m local_fixture tests/test_apply_filesystem_profiles.py
