"""Public own-information and relationship views over a verified Result graph."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path


class ReviewItems(Sequence):
    """Materialize only this call's requested positions, never hash unseen images."""

    def __init__(self, graph, refs):
        self.graph, self.refs, self.cache = graph, refs, {}

    def __len__(self):
        return len(self.refs)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[position] for position in range(*index.indices(len(self)))]
        if index not in self.cache:
            self.cache[index] = review_item(self.graph, self.refs[index])
        return self.cache[index]


def source_lineage(graph, ref, active=None):
    from .read import _ReadFailure

    active = set() if active is None else active
    if ref in active:
        raise _ReadFailure(
            "result_inconsistent", "Evidence derivation contains a cycle."
        )
    active.add(ref)
    sources = set()
    access = graph.evidence[ref].get("access", {})
    if access.get("kind") == "source_item":
        sources.add(access["source_item_ref"])
    for member in graph.members(ref, "derived_from"):
        target = member.get("target", {})
        target_ref = target.get("ref")
        if target.get("kind") == "source_item" and target_ref in graph.sources:
            sources.add(target_ref)
        elif target.get("kind") == "evidence" and target_ref in graph.evidence:
            sources.update(source_lineage(graph, target_ref, active))
        else:
            raise _ReadFailure(
                "result_inconsistent", "Evidence derivation has a missing endpoint."
            )
    if not sources <= graph.sources.keys():
        raise _ReadFailure(
            "result_inconsistent", "Evidence source is outside this Result."
        )
    active.remove(ref)
    return sorted(sources)


def require_evidence_access(graph, ref):
    from .read import _ReadFailure

    access = graph.evidence[ref].get("access", {})
    if access.get("kind") != "local_artifact":
        return
    record = graph.evidence_records[ref]
    proof = graph.artifact_proofs.get(record.get("artifact_id"))
    try:
        if proof is None or graph.workspace is None:
            raise ValueError("No retained Artifact proof")
        root = Path(graph.workspace).resolve()
        path = Path(access["locator"]["value"])
        expected = root / proof["relative_path"]
        if path != expected or not path.resolve().is_relative_to(root):
            raise ValueError("Artifact escapes its retained location")
        if any(
            parent.is_symlink()
            for parent in (path, *path.parents)
            if parent != root and parent.is_relative_to(root)
        ):
            raise ValueError("Artifact path contains a symbolic link")
        from ._result_sqlite import _digest_file

        digest, size = _digest_file(path)
        if size != proof["size_bytes"] or digest != proof["digest"]:
            raise ValueError("Artifact bytes differ from the retained proof")
    except (OSError, ValueError, KeyError) as error:
        raise _ReadFailure(
            "evidence_unavailable",
            "The retained Evidence file is unavailable or no longer matches its sealed identity.",
            details={"evidence_ref": ref},
        ) from error


def review_item(graph, ref):
    from .read import (
        _ReadFailure,
        _represented_refs,
        _observations,
        _evidence_roles,
        _prepared_evidence_refs,
        _capture_time_projection,
        _media_type_projection,
        _qualification_summary_for_members,
        _canonical_json,
    )

    try:
        require_evidence_access(graph, ref)
    except _ReadFailure as error:
        if error.code != "evidence_unavailable":
            raise
        return {
            "evidence_ref": ref,
            "error": {"code": error.code, "message": str(error)},
        }
    evidence = graph.evidence[ref]
    member_refs = _represented_refs(graph, ref)
    members = graph.members(ref, "represents")
    counts = Counter(
        (graph.accounts[source]["scope"], graph.accounts[source]["condition"])
        for source in member_refs
    )
    summaries = []
    for name, projection, has_values in (
        ("capture_time_range", _capture_time_projection, lambda p: "earliest" in p),
        ("media_type_counts", _media_type_projection, lambda p: bool(p["values"])),
    ):
        value = projection(graph, member_refs)
        basis = {"summary": "Computed from the exact members' retained observations."}
        observation = {
            "name": name,
            "status": "available" if has_values(value) else "missing",
            "basis": basis,
        }
        if has_values(value):
            observation["value"] = value
        else:
            basis["status_counts"] = value["status_counts"]
        summaries.append(observation)
    bases = {_canonical_json(member.get("basis")) for member in members}
    common = members[0].get("basis") if members and len(bases) == 1 else None
    represents = {
        "source_set": {
            "kind": "precheck_relation",
            "origin": ref,
            "relation": "represents",
            "direction": "outbound",
        },
        "source_count": len(member_refs),
        "scope_condition": [
            {"scope": scope, "condition": condition, "count": count}
            for (scope, condition), count in sorted(counts.items())
        ],
        "observations": summaries,
        "basis": common
        if common is not None
        else {
            "code": "member_specific"
            if len(bases) > 1
            else "representation_basis_unrecorded",
            "summary": "Inspect each member's covering_evidence for its retained basis.",
        },
    }
    qualifications = _qualification_summary_for_members(members)
    if common is None and len(bases) <= 1:
        qualifications.append(
            {
                "code": "representation_basis_unrecorded",
                "effect": "limits_interpretation",
                "message": "No common representation basis was recorded.",
            }
        )
    if qualifications:
        represents["qualifications"] = qualifications
    sources = source_lineage(graph, ref)
    result = {
        "evidence_ref": ref,
        "access": evidence["access"],
        "observations": list(_observations(evidence)),
        "source_items": [
            {
                "source_item_ref": source,
                "locator": graph.sources[source]["locator"],
                "observations": list(_observations(graph.sources[source])),
                **(
                    {"qualifications": graph.sources[source]["qualifications"]}
                    if graph.sources[source].get("qualifications")
                    else {}
                ),
            }
            for source in sources
        ],
        "represents": represents,
        "available_expansions": [],
    }
    own_qualifications = list(evidence.get("qualifications", ()))
    if not sources:
        own_qualifications.append(
            {
                "code": "source_lineage_unavailable",
                "effect": "limits_interpretation",
                "message": "This Evidence has no recorded content Source Item lineage.",
            }
        )
    if own_qualifications:
        result["qualifications"] = own_qualifications
    prepared = graph.members(ref, "expands_to")
    prepared_refs = sorted(set(_prepared_evidence_refs(prepared)) - {ref})
    roles = {}
    unassigned = []
    for target in prepared_refs:
        target_roles = _evidence_roles(graph.evidence[target])
        if not target_roles:
            unassigned.append(target)
        for role in target_roles:
            roles.setdefault(role, []).append(target)
    if roles:
        result["roles"] = roles
    if unassigned:
        result["unassigned_prepared_evidence"] = unassigned
    for include, count in (
        ("prepared_targets", len(prepared)),
        ("provenance", len(graph.members(ref, "derived_from"))),
        ("coverage_basis", len(members)),
        ("member_observations", len(members)),
    ):
        if count:
            result["available_expansions"].append(
                {"include": include, "estimated_items": count}
            )
    return result


def project_retained_observations(graph, *, historical):
    """Adapt sealed historical values without changing bytes or acquiring evidence."""
    work_refs = {
        record.get("work_id"): ref
        for ref, record in graph.evidence_records.items()
        if record.get("work_id")
    }
    for view in (*graph.sources.values(), *graph.evidence.values()):
        observations = []
        historical_gaps = {}
        role_seen = False
        for original in view.get("observations", ()):
            item = dict(original)
            value = item.get("value")
            if historical and isinstance(value, dict):
                value = dict(value)
                item["value"] = value
                name = item["name"]
                if name == "source_content_verification":
                    value.pop("status", None)
                if name == "evidence_role":
                    value.pop("group_ref", None)
                if name == "video_contact_sheet" and "frame_work_ids" in value:
                    ids = value.pop("frame_work_ids")
                    frames = []
                    for work_id in ids:
                        target = work_refs.get(work_id)
                        if target is None:
                            from .read import _ReadFailure

                            raise _ReadFailure(
                                "result_inconsistent",
                                "A retained contact-sheet input is missing.",
                            )
                        frame = next(
                            o["value"]
                            for o in graph.evidence[target].get("observations", ())
                            if o["name"] == "video_frame"
                        )
                        frames.append(
                            {
                                "evidence_ref": target,
                                "sample_time_seconds": frame["sample_time_seconds"],
                            }
                        )
                    value["frames"] = frames
            if item["name"] == "evidence_role":
                if role_seen:
                    view.setdefault("qualifications", []).append(
                        {
                            "code": "additional_evidence_role",
                            "effect": "limits_interpretation",
                            "message": "The retained Evidence also has this role.",
                            "basis": value,
                        }
                    )
                    continue
                role_seen = True
            if (
                historical
                and item["name"] == "content_sensitivity"
                and item["status"] in {"available", "failed"}
            ):
                raw_provenance = item.get("provenance")
                provenance = (
                    dict(raw_provenance)
                    if isinstance(raw_provenance, dict)
                    else {"retained_provenance": raw_provenance}
                )
                input_id = provenance.pop("input_work_id", None)
                target = work_refs.get(input_id)
                if target:
                    provenance["input_evidence_ref"] = target
                item["provenance"] = provenance
                if item["status"] in {"available", "failed"} and not provenance.get(
                    "input_evidence_ref"
                ):
                    retained_value = item.get("value", {})
                    detector = retained_value.get(
                        "detector_identity", provenance.get("detector_identity")
                    )
                    # Unknown inputs cannot acquire invented Evidence identities.
                    # Keep one gap per proven detector, with each original record
                    # separately retained; this is not an aggregate detection.
                    if detector not in historical_gaps:
                        gap = {
                            "name": "content_sensitivity",
                            "status": "not_checked",
                            "provenance": {"detector_identity": detector}
                            if detector is not None
                            else {},
                            "basis": {
                                "code": "historical_unrecorded",
                                "summary": "These historical detection records cannot be bound to public input Evidence; they are not a whole-source detection.",
                                "retained_observations": [],
                            },
                            "qualifications": [
                                {
                                    "code": "historical_sensitivity_inputs_unrecorded",
                                    "effect": "limits_interpretation",
                                    "message": "Per-record outcomes remain evidence, but their original input samples cannot be identified.",
                                }
                            ],
                        }
                        historical_gaps[detector] = gap
                        observations.append(gap)
                    historical_gaps[detector]["basis"]["retained_observations"].append(
                        item
                    )
                    continue
                else:
                    item["provenance"] = provenance
            if (
                historical
                and item["status"] in {"not_checked", "not_applicable"}
                and "basis" not in item
            ):
                item["basis"] = {"code": "historical_unrecorded"}
            observations.append(item)
        view["observations"] = observations

    if historical:
        from ._metadata_fields import FIELD_TAGS

        for ref, view in graph.sources.items():
            if graph.accounts[ref].get("scope") != "source_media":
                continue
            names = {o["name"] for o in view["observations"]}
            expected = {
                *FIELD_TAGS,
                "capture_time",
                "gps_coordinates",
                "source_pixel_dimensions",
                "content_sensitivity",
            }
            for name in sorted(expected - names):
                view["observations"].append(
                    {
                        "name": name,
                        "status": "not_checked",
                        "basis": {"code": "historical_unrecorded"},
                    }
                )
