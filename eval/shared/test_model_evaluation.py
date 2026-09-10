"""Focused accounting, correspondence, sampling, and offline recipe checks."""

import json
import math
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from model_evaluation import inference_fingerprint, timed_batch, validate_vector
from model_evaluation_inputs import (
    checked_file,
    digest,
    nearest_frames,
    prepare_inputs,
    source_rows,
    validate_inputs,
)
from model_evaluation_hierarchy import leaf_members, linear_hierarchical


class ModelEvaluationTests(unittest.TestCase):
    def classification_inputs(self, angles):
        records = [
            {"id": str(index), "source": str(index), "timestamp": index}
            for index in range(len(angles))
        ]
        vectors = {
            str(index): (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
            for index, angle in enumerate(angles)
        }
        return records, vectors

    def test_historical_adjacent_splits_restore_time_order(self):
        records, vectors = self.classification_inputs([0, 10, 90, 100, 180])
        tree = linear_hierarchical(
            records[::-1], vectors, {"distance_levels": [0.5], "min_cluster_weight": 0}
        )
        self.assertEqual(
            [leaf_members(child) for child in tree["children"]],
            [["0", "1"], ["2", "3"], ["4"]],
        )

    def test_historical_weight_boundary_and_early_stop_are_not_reinterpreted(self):
        records, vectors = self.classification_inputs([0, 180] * 12 + [0])
        tree = linear_hierarchical(
            records, vectors, {"distance_levels": [0.311], "min_cluster_weight": 20}
        )
        self.assertEqual(
            [len(leaf_members(child)) for child in tree["children"]], [19, 6]
        )
        small = linear_hierarchical(
            records[:20],
            {row["id"]: vectors[row["id"]] for row in records[:20]},
            {"distance_levels": [0.311], "min_cluster_weight": 20},
        )
        self.assertEqual(len(small["members"]), 20)
        records, vectors = self.classification_inputs([0, 40, 80])
        stopped = linear_hierarchical(
            records, vectors, {"distance_levels": [0.9, 0.1], "min_cluster_weight": 0}
        )
        self.assertEqual(stopped["members"], ["0", "1", "2"])

    def test_tree_requires_every_input_vector_once(self):
        records, vectors = self.classification_inputs([0, 90])
        del vectors["1"]
        with self.assertRaisesRegex(ValueError, "exactly one matching vector"):
            linear_hierarchical(
                records, vectors, {"distance_levels": [0.311], "min_cluster_weight": 20}
            )

    def test_sparse_video_positions_bind_real_indices(self):
        probe = {
            "format": {"duration": "3"},
            "frames": [
                {"best_effort_timestamp_time": str(index)} for index in range(3)
            ],
        }
        self.assertEqual(
            nearest_frames(probe, [0.1, 0.5, 0.9]), [(0, 0.0), (1, 1.0), (2, 2.0)]
        )
        probe["frames"] = probe["frames"][:1]
        self.assertEqual(nearest_frames(probe, [0.1, 0.5, 0.9]), [(0, 0.0)] * 3)

    def test_batch_order_and_completion_are_preserved(self):
        class Adapter:
            synchronizations = 0

            def synchronize(self):
                self.synchronizations += 1
                if self.synchronizations == 2:
                    time.sleep(0.02)

            def encode_images(self, paths):
                return [(float(path.name), 1) for path in paths]

        adapter = Adapter()
        rows, elapsed = timed_batch(adapter, [Path("9"), Path("2"), Path("7")])
        self.assertEqual(rows, ((9.0, 1.0), (2.0, 1.0), (7.0, 1.0)))
        self.assertEqual(adapter.synchronizations, 2)
        self.assertGreaterEqual(
            elapsed, 0.018, "Completion wait must be inside the timer"
        )

    def test_short_batch_fails_before_assigning_rows(self):
        class Adapter:
            def synchronize(self):
                pass

            def encode_images(self, paths):
                return [(1, 2)]

        with self.assertRaisesRegex(ValueError, "output count"):
            timed_batch(Adapter(), [Path("first"), Path("second")])

    def test_invalid_vectors_fail_and_valid_vectors_round_trip(self):
        for vector in ((0, 0), (float("nan"), 1), (float("inf"), 1), (1,)):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                validate_vector(vector, 2)
        result = validate_vector((3, 4), 2)
        self.assertAlmostEqual(result[0], 0.6, places=6)
        self.assertAlmostEqual(result[1], 0.8, places=6)

    def fixture(self, root):
        (root / "manifests").mkdir()
        (root / "media").mkdir()
        Image.new("RGB", (32, 20), "red").save(root / "media" / "original.jpg")
        manifest = root / "manifests/media-manifest.jsonl"
        manifest.write_text(
            json.dumps(
                {
                    "path": "original.jpg",
                    "media_type": "image",
                    "derived_sha256": digest(root / "media/original.jpg"),
                    "cached_metadata": {"old_caption": "must not enter inputs"},
                }
            )
        )
        checksums = root / "manifests/SHA256SUMS"
        checksums.write_text("test-only fixture checksum list")
        (root / "media/old-output.jpg").write_bytes(b"excluded")
        return {
            "fixture": {
                "package_root": str(root),
                "media_subdirectory": "media",
                "checksum_manifest_sha256": digest(checksums),
                "media_manifest_sha256": digest(manifest),
                "expected_media_count": 1,
            },
            "inputs": {
                "video_fractions": [0.1, 0.5, 0.9],
                "ffmpeg": "ffmpeg",
                "ffprobe": "ffprobe",
                "tool_versions": {"ffmpeg": "test", "ffprobe": "test"},
            },
            "expected_input_fingerprint": None,
            "model": {"dimensions": 2, "revision": "one"},
            "runtime": {},
            "classification": {"distance_levels": [0.311]},
        }

    def test_allowlist_excludes_old_outputs_and_source_change_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.fixture(root)
            _, rows = source_rows(config)
            self.assertEqual([row["path"] for row in rows], ["original.jpg"])
            self.assertNotIn("cached_metadata", rows[0])
            (root / "media/original.jpg").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                source_rows(config)

    def test_paths_cannot_escape_or_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").write_text("original")
            (root / "alias").symlink_to(root / "source")
            for name in ("../source", str(root / "source"), "alias"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    checked_file(root, name, digest(root / "source"))

    def test_prepared_ids_and_pixels_are_verified_again_before_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture"
            source.mkdir()
            config = self.fixture(source)
            target = root / "prepared"
            with patch("model_evaluation_inputs.tool_version", return_value="test"):
                result = prepare_inputs(config, target)
            config["expected_input_fingerprint"] = result["input_fingerprint"]
            value = validate_inputs(config, target / "inputs.json")
            self.assertEqual(len(value["inputs"]), 1)
            value["inputs"].append(value["inputs"][0])
            (target / "inputs.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(
                ValueError, "missing, reordered, or duplicated"
            ):
                validate_inputs(config, target / "inputs.json")

    def test_vector_identity_does_not_depend_only_on_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.fixture(Path(directory))
            before = inference_fingerprint(config)
            config["model"]["revision"] = "two"
            self.assertNotEqual(before, inference_fingerprint(config))
            after = inference_fingerprint(config)
            config["classification"]["distance_levels"] = [0.2]
            self.assertEqual(
                after,
                inference_fingerprint(config),
                "Classification is separately bound to its own config",
            )


if __name__ == "__main__":
    unittest.main()
