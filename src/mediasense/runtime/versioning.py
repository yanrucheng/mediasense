"""Independent persistent-format version declarations."""

from __future__ import annotations

from mediasense.version import application_version as application_version

DATASET_MANIFEST_VERSION = 3
DATASET_STORE_VERSIONS = {
    "apply": 2,
    "geo": 2,
    "plan": 3,
    "precheck": 18,
}
