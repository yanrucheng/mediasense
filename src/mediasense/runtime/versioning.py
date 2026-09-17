"""Independent persistent-format version declarations."""

from __future__ import annotations

from mediasense.version import application_version as application_version

DATASET_MANIFEST_VERSION = 3
DATASET_STORE_VERSIONS = {
    "apply": 3,
    "geo": 2,
    "plan": 4,
    "precheck": 19,
}
