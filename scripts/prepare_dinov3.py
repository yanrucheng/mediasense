#!/usr/bin/env python3
"""Copy an already verified DINOv3 384 Core ML export into a local model home.

No download, conversion, Dataset changes or configuration enablement. The source
can be the accepted evaluation export or an exact independently retained copy.
"""

import argparse
from pathlib import Path
import shutil
import tempfile

from mediasense.precheck.dinov3 import default_model_path, verify_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=default_model_path())
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.absolute()
    verify_model(source)
    if destination.exists():
        verify_model(destination)
        print(f"Already prepared and verified: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".dinov3-prepare-", dir=destination.parent))
    try:
        shutil.copytree(source / "vision.mlmodelc", staging / "vision.mlmodelc")
        verify_model(staging)
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f"Prepared and verified: {destination}")


if __name__ == "__main__":
    main()
