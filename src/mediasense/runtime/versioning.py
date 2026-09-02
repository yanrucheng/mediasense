"""Independent persistent-format version declarations."""

from __future__ import annotations

from mediasense.version import application_version as application_version

DATASET_MANIFEST_VERSION = 1
DATASET_STORE_VERSIONS = {
    "apply": 2,
    "geo": 1,
    "plan": 2,
    "precheck": 16,
}
