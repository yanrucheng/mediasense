from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from mediasense.precheck.scope_review import build_scope_inventory

MODULE = Path(__file__).parents[1] / "eval/shared/prepare_input.py"
spec = importlib.util.spec_from_file_location("prepare_input", MODULE)
prepare_input = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_input)


def test_scope_does_not_preview_descendant_labels_but_explicit_navigation_can():
    facts = [
        {
            "relative_path": "prior/OLD_ANSWER/photo.jpg",
            "kind": "image",
            "size_bytes": 3,
        }
    ]
    shallow = build_scope_inventory(facts, (), scan_generation=1)
    assert "OLD_ANSWER" not in json.dumps(shallow)
    assert shallow["view"]["entries"][0]["file_count"] == 1
    assert "OLD_ANSWER" in json.dumps(
        build_scope_inventory(facts, (), scan_generation=1, scope_path="prior")
    )


def test_scope_error_does_not_echo_descendant_label():
    issues = [
        {
            "relative_path": "prior/OLD_ANSWER/bad",
            "code": "permission_denied",
            "blocked": True,
            "basis": ["Cannot read prior/OLD_ANSWER/bad"],
        }
    ]
    view = build_scope_inventory([], issues, scan_generation=1)
    assert "OLD_ANSWER" not in json.dumps(view)
    assert view["issues"][0] == {
        "path": "prior",
        "code": "permission_denied",
        "message": "permission_denied",
    }


def test_allowlist_isolates_samples_accounting_errors_and_paths(tmp_path):
    source = tmp_path / "source"
    (source / "human-label").mkdir(parents=True)
    (source / "human-label/photo.jpg").write_bytes(b"media")
    (source / "OLD_ANSWER-caption.txt").write_text("OLD_ANSWER")
    (source / "prior/OLD_ANSWER").mkdir(parents=True)
    (source / "prior/OLD_ANSWER/prior.jpg").write_bytes(b"old")
    allowed = {"human-label/photo.jpg": hashlib.sha256(b"media").hexdigest()}
    manifest = prepare_input.prepare(
        source, allowed, tmp_path / "prepared", path_policy="preserve"
    )
    assert manifest["path_policy"] == "preserve"
    assert [
        str(p.relative_to(tmp_path / "prepared"))
        for p in (tmp_path / "prepared").rglob("*")
        if p.is_file()
    ] == ["human-label/photo.jpg"]
    opaque = prepare_input.prepare(
        source, allowed, tmp_path / "opaque", path_policy="opaque"
    )
    assert opaque["allowed"][0]["staged"] == "item-000000.jpg"
    assert not any("human-label" in str(p) for p in (tmp_path / "opaque").rglob("*"))
    assert (source / "OLD_ANSWER-caption.txt").exists()
    with pytest.raises(ValueError, match="row 0") as error:
        prepare_input.prepare(
            source,
            {"OLD_ANSWER-caption.txt": "wrong"},
            tmp_path / "bad",
            path_policy="preserve",
        )
    assert "OLD_ANSWER" not in str(error.value)
    (source / "link.jpg").symlink_to(source / "human-label/photo.jpg")
    with pytest.raises(ValueError, match="Non-regular"):
        prepare_input.prepare(
            source,
            {"link.jpg": allowed["human-label/photo.jpg"]},
            tmp_path / "links",
            path_policy="preserve",
        )
    assert not (tmp_path / "links").exists()


def test_rejects_traversal_and_mutation_of_fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="outside"):
        prepare_input.prepare(
            source, {"x.jpg": "hash"}, source / "outputs", path_policy="preserve"
        )
    with pytest.raises(ValueError, match="Invalid allowlist"):
        prepare_input.prepare(
            source, {"../x.jpg": "hash"}, tmp_path / "prepared", path_policy="opaque"
        )


@pytest.mark.parametrize(
    "alias", ["dotdot", "parent_symlink", "leaf_symlink", "source_tree"]
)
def test_cli_refuses_manifest_alias_into_judged_or_original_source_before_copy(
    tmp_path, alias
):
    original = tmp_path / "original"
    original.mkdir()
    (original / "photo.jpg").write_bytes(b"media")
    allowlist = tmp_path / "allowed.json"
    allowlist.write_text(
        json.dumps({"photo.jpg": hashlib.sha256(b"media").hexdigest()})
    )
    destination = tmp_path / "source"
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    if alias == "dotdot":
        output = metadata / ".." / "source" / "operator.json"
    elif alias == "parent_symlink":
        (metadata / "alias").symlink_to(destination, target_is_directory=True)
        output = metadata / "alias/operator.json"
    elif alias == "leaf_symlink":
        output = metadata / "operator.json"
        output.symlink_to(destination / "operator.json")
    else:
        output = original / "operator.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE),
            "--source-root",
            str(original),
            "--allowlist",
            str(allowlist),
            "--destination",
            str(destination),
            "--path-policy",
            "opaque",
            "--operator-manifest",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "outside" in completed.stderr
    assert not destination.exists()
    assert sorted(p.name for p in original.iterdir()) == ["photo.jpg"]


def test_manifest_write_rechecks_alias_and_refuses_existing_output(tmp_path):
    source = tmp_path / "original"
    source.mkdir()
    target = tmp_path / "judged"
    target.mkdir()
    parent = tmp_path / "metadata"
    parent.mkdir()
    output = parent / "operator.json"
    prepare_input.operator_manifest_path(source, target, output)
    parent.rmdir()
    parent.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="outside"):
        prepare_input.write_operator_manifest(
            source, target, output, {"private": "name"}
        )
    assert list(target.iterdir()) == []
    good = tmp_path / "operator.json"
    prepare_input.write_operator_manifest(source, target, good, {"allowed": []})
    before = good.read_bytes()
    assert good.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="new regular"):
        prepare_input.write_operator_manifest(source, target, good, {"different": True})
    assert good.read_bytes() == before


def test_manifest_leaf_symlink_race_is_not_followed(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "judged"
    target.mkdir()
    output = tmp_path / "operator.json"
    real_open = os.open

    def racing_open(path, flags, *args, **kwargs):
        if path == output.name and flags & os.O_CREAT:
            output.symlink_to(target / "leaked.json")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(prepare_input.os, "open", racing_open)
    with pytest.raises(FileExistsError):
        prepare_input.write_operator_manifest(
            source, target, output, {"private": "name"}
        )
    assert not (target / "leaked.json").exists()
