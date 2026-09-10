"""Business correspondence and replacement checks without model downloads."""

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from model_evaluation import timed_batch, validate_vector
from model_evaluation_business import (
    business_code,
    check_baseline,
    classify,
    comparison_identity,
)
from model_evaluation_business_preview import render_business


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "inputs": {"business_code": business_code(), "compression_target": 200},
            "classification": {
                "status": "confirmed",
                "algorithm": "mediasense_content_boundaries_with_anchor",
                "video_top_k": 0.5,
                "profile": {"target_entries": 200, "content_based_boundaries": True},
            },
            "model": {"model_id": "test/model"},
            "runtime": {"device": "cpu", "precision": "float32", "batch_size": 4},
            "baseline_ref": None,
        }
        self.prepared = {
            "input_fingerprint": "fixed-inputs",
            "inputs": [
                {
                    "id": "a",
                    "source": "a.jpg",
                    "kind": "image",
                    "state": "ready",
                    "sample_time_seconds": None,
                },
                *[
                    {
                        "id": f"v{i}",
                        "source": "v.mp4",
                        "kind": "video",
                        "state": "ready",
                        "sample_time_seconds": i,
                    }
                    for i in range(3)
                ],
                {
                    "id": "bad",
                    "source": "bad.mp4",
                    "kind": "video",
                    "state": "failed",
                    "sample_time_seconds": None,
                    "error": "unreadable",
                },
            ],
            "business": {
                "sources": {
                    name: {
                        "kind": "video" if name.endswith("mp4") else "image",
                        "capture_time": f"2026-05-01T12:{index:02d}:00+08:00",
                        "gps": None,
                        "visual_requested": name != "hidden.jpg",
                    }
                    for index, name in enumerate(
                        ["a.jpg", "v.mp4", "hidden.jpg", "bad.mp4"]
                    )
                },
                "bundles": [
                    {
                        "id": "b1",
                        "selected": True,
                        "representative": "a.jpg",
                        "members": ["a.jpg", "hidden.jpg"],
                    },
                    {
                        "id": "b2",
                        "selected": True,
                        "representative": "bad.mp4",
                        "members": ["bad.mp4", "v.mp4"],
                    },
                ],
            },
        }
        self.vectors = {
            "a": (1.0, 0.0),
            "v0": (0.0, 1.0),
            "v1": (0.1, 0.99),
            "v2": (1.0, 0.0),
        }

    def test_same_points_match_direct_business_and_fallback(self):
        from mediasense.precheck.compression import (
            CompressionPoint,
            AdaptiveCompressionProfile,
            build_adaptive_groups,
            select_embedding_representative,
        )

        result = classify(self.config, self.prepared, self.vectors)
        selected = select_embedding_representative(
            [self.vectors[f"v{i}"] for i in range(3)], top_k=0.5
        )
        self.assertEqual(result["selected_inputs"]["v.mp4"], f"v{selected}")
        self.assertEqual(result["point_count"], 2)
        self.assertEqual(result["grouped_sources"], 4)
        self.assertTrue(result["bundle_selection"][1]["preferred_replaced"])
        points = [
            CompressionPoint(
                Path(source),
                datetime.fromisoformat(
                    self.prepared["business"]["sources"][source]["capture_time"]
                ),
                embedding=vector,
                members=tuple(map(Path, members)),
                weight=len(members),
            )
            for source, vector, members in [
                ("a.jpg", self.vectors["a"], ["a.jpg", "hidden.jpg"]),
                ("v.mp4", self.vectors[f"v{selected}"], ["bad.mp4", "v.mp4"]),
            ]
        ]
        direct = build_adaptive_groups(
            points,
            AdaptiveCompressionProfile(**self.config["classification"]["profile"]),
        )
        self.assertEqual(
            [g["members"] for g in result["groups"]],
            [[p.as_posix() for p in g.members] for g in direct],
        )
        self.assertEqual(
            [g["representative_path"] for g in result["groups"]],
            [g.representative_path.as_posix() for g in direct],
        )
        self.assertEqual(result, classify(self.config, self.prepared, self.vectors))

    def test_model_change_can_change_frame_selection_without_changing_recipe(self):
        original = classify(self.config, self.prepared, self.vectors)
        changed = dict(self.vectors, v0=(1.0, 0.0), v1=(0.0, 1.0), v2=(0.1, 0.99))
        candidate = classify(self.config, self.prepared, changed)
        self.assertNotEqual(
            original["selected_inputs"]["v.mp4"], candidate["selected_inputs"]["v.mp4"]
        )
        identity = comparison_identity(self.config, self.prepared)
        self.config["model"] = {"model_id": "different/framework", "dimensions": 900}
        self.assertEqual(identity, comparison_identity(self.config, self.prepared))

    def test_changed_algorithm_parameters_refuse_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(
                json.dumps(
                    {
                        "classification_fingerprint": comparison_identity(
                            self.config, self.prepared
                        )
                    }
                )
            )
            self.config["baseline_ref"] = str(path)
            check_baseline(self.config, self.prepared)
            self.config["classification"]["profile"]["content_distance_scale"] = 0.2
            with self.assertRaisesRegex(ValueError, "different business"):
                check_baseline(self.config, self.prepared)

    def test_missing_vector_is_not_silently_discarded(self):
        del self.vectors["v0"]
        with self.assertRaisesRegex(ValueError, "exactly"):
            classify(self.config, self.prepared, self.vectors)

    def test_no_available_member_remains_explicit_exception(self):
        self.prepared["inputs"] = [
            r
            for r in self.prepared["inputs"]
            if r["kind"] != "video" or r["state"] == "failed"
        ]
        result = classify(self.config, self.prepared, {"a": self.vectors["a"]})
        self.assertEqual(result["exceptions"], ["bad.mp4", "v.mp4"])

    def test_framework_free_second_adapter_and_preview(self):
        from PIL import Image

        class Adapter:
            def synchronize(self):
                pass

            def encode_images(self, paths):
                return [(index + 1, 1) for index, _ in enumerate(paths)]

        raw, _ = timed_batch(Adapter(), [Path("x"), Path("y")])
        self.assertEqual(len(raw), 2)
        self.assertEqual(len(validate_vector(raw[0], 2)), 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepared["source_root"] = str(root)
            for source in self.prepared["business"]["sources"]:
                if source.endswith("jpg"):
                    Image.new("RGB", (20, 20), "red").save(root / source)
                else:
                    (root / source).write_bytes(b"test-video")
            for row in self.prepared["inputs"]:
                if row["state"] == "ready":
                    row["image_path"] = str(root / (row["id"] + ".jpg"))
                    Image.new("RGB", (20, 20), "blue").save(row["image_path"])
            result = classify(self.config, self.prepared, self.vectors)
            encoded = {
                "runtime": dict(self.config["runtime"]),
                "counts": {"encoded": 4},
                "performance": {
                    "model_load_seconds": 1.0,
                    "encoding_seconds": 2.0,
                    "inputs_per_second": 2.0,
                    "peak_process_rss_bytes": 1000,
                },
            }
            rendered = render_business(
                root / "preview", self.prepared, result, encoded, self.config
            )
            page = (root / "preview/index.html").read_text()
            self.assertEqual(rendered["source_cards"], 4)
            self.assertEqual(page.count('class="frame chosen"'), 1)
            self.assertIn("未请求编码", page)
            self.assertIn("unreadable", page)
            self.assertFalse(rendered["thumbnail_failures"])

    def test_preview_uses_recorded_runtime_and_effective_encoder(self):
        cases = [
            (
                "cpu",
                {"device": "cpu", "precision": "float32", "batch_size": 4},
                {"mps_available": True},
                "CPU · float32 · batch 4",
            ),
            (
                "mps",
                {"device": "mps", "precision": "float16", "batch_size": 8},
                {},
                "MPS · float16 · batch 8",
            ),
            (
                "effective",
                {"device": "mps", "precision": "float16", "batch_size": 8},
                {"device": "cpu", "precision": "float32; reported by adapter"},
                "CPU · float32; reported by adapter · batch 8",
            ),
            (
                "escaped",
                {"device": "mps", "precision": "float16", "batch_size": 8},
                {"device": "gpu <custom>", "precision": 'float16 & "mixed"'},
                "GPU &lt;CUSTOM&gt; · float16 &amp; &quot;mixed&quot; · batch 8",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = {
                "source_root": str(root),
                "inputs": [],
                "business": {"sources": {}, "bundles": []},
            }
            result = {"groups": [], "exceptions": [], "point_count": 0}
            for name, runtime, effective, expected in cases:
                with self.subTest(name=name):
                    encoded = {
                        "runtime": runtime,
                        "effective_encoder": effective,
                        "counts": {"encoded": 0},
                        "performance": {
                            "model_load_seconds": 1.0,
                            "encoding_seconds": 2.0,
                            "inputs_per_second": 0.0,
                            "peak_process_rss_bytes": 1000,
                        },
                    }
                    render_business(root / name, prepared, result, encoded, self.config)
                    page = (root / name / "index.html").read_text()
                    self.assertIn(f"<p>model · {expected}</p>", page)


if __name__ == "__main__":
    unittest.main()
