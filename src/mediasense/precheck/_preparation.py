"""Complete Processing Profile values and their frozen Run/Result projection.

This is a value boundary, not a Profile store. Read owns Source Set interpretation;
the composition root supplies installed recipes without loading model weights.
"""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from ._compression_strategy import AdaptiveCompressionProfile


def installed_preparation_recipes():
    """Installed producer declarations, shared by direct and Host composition."""
    from importlib.metadata import PackageNotFoundError, version
    from PIL import __version__, features
    from .rendition import ORDINARY_RENDITION_PROFILE, HIGH_RESOLUTION_RENDITION_PROFILE
    from ._video_types import ContactSheetProfile, VideoFrameProfile
    from .metadata import PRODUCER_IDENTITY as metadata_recipe
    from .rendition import PRODUCER_IDENTITY as rendition_recipe
    from .gpx import PRODUCER_IDENTITY as gpx_recipe, GPXMatchProfile
    from .bundling import PRODUCER_IDENTITY as bundle_recipe, BundleProfile
    from ._compression_producer import PRODUCER_IDENTITY as compression_recipe
    from .geocode import _PRODUCER as geo_recipe, acquisition_policy_value

    def package(name):
        try:
            return version(name)
        except PackageNotFoundError:
            return "unavailable"

    return {
        "metadata": {"producer": metadata_recipe, "fields": "typed-source-fields-v2"},
        "gpx": {
            "producer": gpx_recipe,
            "gpxpy": package("gpxpy"),
            "profile": asdict(GPXMatchProfile()),
        },
        "image_renditions": {
            "producer": rendition_recipe,
            "pillow": __version__,
            "jpeg": features.version_codec("jpg"),
            "profiles": [
                asdict(ORDINARY_RENDITION_PROFILE),
                asdict(HIGH_RESOLUTION_RENDITION_PROFILE),
            ],
        },
        "video": {
            "probe": "builtin-ffprobe-video-v1",
            "frame": "builtin-pts-video-frame-v2",
            "sheet": "builtin-video-contact-sheet-v1",
            "av": package("av"),
            "frame_profile": asdict(VideoFrameProfile()),
            "sheet_profile": asdict(ContactSheetProfile()),
        },
        "bundles": {"producer": bundle_recipe, "profile": asdict(BundleProfile())},
        "visual_selection": "builtin-bounded-initial-selection-v1",
        "bundle_partition": "directed-members-with-base-remainder-v1",
        "geo": {"producer": geo_recipe, "acquisition": acquisition_policy_value()},
        "compression_recipe": {
            "producer": compression_recipe,
            "coordinates": "gpx-coordinate-v1",
        },
    }


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def resolved_preparation_recipes(config, dependencies):
    """Resolve output-affecting installed executables without acquiring inputs."""
    import subprocess

    recipes = deepcopy(
        dependencies.preparation_recipes or installed_preparation_recipes()
    )

    def version(executable, argument, declared, runner):
        if declared is not None:
            return declared
        try:
            run = runner or (
                lambda command: subprocess.run(
                    command, capture_output=True, text=True, check=False
                )
            )
            output = run((executable, argument))
            return (
                output.stdout.strip().splitlines()[0]
                if output.returncode == 0 and output.stdout.strip()
                else "unavailable"
            )
        except OSError:
            return "unavailable"

    if config.metadata:
        recipes["metadata"] = {
            "recipe": recipes["metadata"],
            "exiftool": version(
                "exiftool",
                "-ver",
                dependencies.exiftool_version,
                dependencies.metadata_runner,
            ),
        }
    if config.video:
        recipes["video"] = {
            "recipe": recipes["video"],
            "ffprobe": version(
                "ffprobe",
                "-version",
                dependencies.ffprobe_version,
                dependencies.video_runner,
            ),
        }
    return recipes


def preparation_configuration_identity(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def preparation_configuration_value(config, recipes):
    """Pure semantic projection of a resolved execution config and recipe values."""
    embedding = config["embedding_profile"]
    if embedding is not None and not config.get("embedding_encoder_identity"):
        raise ValueError("Enabled embedding needs an immutable encoder declaration")
    profiles = config.get("sensitivity_profiles", [])
    identities = config.get("sensitivity_detector_identities", [])
    if len(profiles) != len(identities) or any(not i for i in identities):
        raise ValueError("Enabled detectors need immutable declarations")
    enabled = sorted(
        (
            {
                "identity": identity,
                "profile": {
                    k: v
                    for k, v in profile.items()
                    if k
                    not in {"batch_size", "memory_bytes", "model_path", "cpu_threads"}
                },
            }
            for identity, profile in zip(identities, profiles, strict=True)
        ),
        key=lambda item: item["identity"],
    )
    sensitivity = config.get("sensitivity_configuration") or {}
    disabled = sorted(
        name
        for name, model in sensitivity.get("models", {}).items()
        if not sensitivity.get("enabled", False) or not model.get("enabled", False)
    )
    fixed = asdict(AdaptiveCompressionProfile(target_entries=1))
    for key in compression_parameters(1):
        fixed.pop(key)
    fixed["content_based_boundaries"] = embedding is not None
    if config["bundles"]:
        fixed["bundle_partition_recipe"] = recipes["bundle_partition"]
    values = {
        "metadata": {
            "enabled": config["metadata"],
            "profile": config["metadata_profile"],
            "recipe": recipes["metadata"],
        },
        "gpx": {"enabled": config["gpx"], "recipe": recipes["gpx"]},
        "image_renditions": {
            "enabled": config["image_renditions"],
            "recipe": recipes["image_renditions"],
        },
        "video": {
            "enabled": config["video"],
            "frame_limit": config["video_frame_limit"],
            "recipe": recipes["video"],
        },
        "bundles": {"enabled": config["bundles"], "recipe": recipes["bundles"]},
        "visual_selection": {
            "recipe": recipes["visual_selection"],
            "base_target": config["compression_target"],
            "directed_inputs": config["directed_evidence_paths"],
        },
        "embedding": None
        if embedding is None
        else {
            "profile": embedding,
            "encoder_identity": config["embedding_encoder_identity"],
        },
        "sensitivity": {"enabled": enabled, "disabled": disabled},
        "geo": {"profile": config["reverse_geocode_profile"], "recipe": recipes["geo"]},
        "compression_recipe": {
            "recipe": recipes["compression_recipe"],
            "settings": fixed,
        },
    }
    # Detach values from mutable caller-owned dictionaries and reject non-JSON.
    return json.loads(canonical({"kind": "precheck-preparation", "values": values}))


def compression_parameters(target):
    if target is None:
        return None
    p = AdaptiveCompressionProfile(target_entries=target)
    return {
        k: getattr(p, k)
        for k in (
            "target_entries",
            "temporal_scale_seconds",
            "spatial_scale_meters",
            "content_distance_scale",
        )
    }


def freeze_preparation(request, config, recipes, graph=None, result_digest=None):
    """Validate against trusted immutable input, without scanning or effects."""
    from .read import _ReadFailure, _resolve_source_set, _resolved_member

    requested = {k: request[k] for k in ("source_set", "profile") if k in request}
    try:
        request_size = len(canonical(requested).encode("utf-8"))
    except (ValueError, TypeError, RecursionError) as error:
        raise _ReadFailure(
            "invalid_request", "Preparation must be finite canonical JSON."
        ) from error
    if request_size > 262144:
        raise _ReadFailure(
            "invalid_request", "Preparation request exceeds 262144 bytes."
        )
    try:
        projection = preparation_configuration_value(config, recipes)
    except ValueError as error:
        raise _ReadFailure("configuration_invalid", str(error)) from error
    identity = preparation_configuration_identity(projection)
    profile = deepcopy(
        request.get(
            "profile",
            {
                "configuration_identity": identity,
                "compression": compression_parameters(config["compression_target"]),
                "overrides": [],
            },
        )
    )
    if profile["configuration_identity"] != identity:
        raise _ReadFailure(
            "configuration_changed",
            "Current preparation semantics differ from the supplied configuration identity.",
        )
    scopes, inputs = [], None
    if "source_set" in request:
        if graph is None or _resolve_source_set(graph, request["source_set"]) != set(
            graph.accounts
        ):
            raise _ReadFailure(
                "invalid_source_set",
                "Input snapshot must select every accounted Source Item.",
            )
        inputs = []
        records = graph.source_records
        for ref in sorted(graph.accounts):
            member = _resolved_member(graph, ref)
            inputs.append(
                {**member, "accounting": deepcopy(records[ref].get("accounting"))}
            )
    occupied = set()
    for override in profile["overrides"]:
        if inputs is None:
            raise _ReadFailure(
                "invalid_source_set", "Overrides require an explicit input snapshot."
            )
        members = _resolve_source_set(graph, override["source_set"])
        if (
            not members
            or members & occupied
            or any(
                graph.accounts[ref]["scope"] != "source_media"
                or graph.accounts[ref]["condition"] not in {"usable", "unresolved"}
                for ref in members
            )
        ):
            raise _ReadFailure(
                "invalid_source_set",
                "Overrides must select disjoint nonempty processable media.",
            )
        base, changed = profile["compression"], override["compression"]
        base_distance = (base or compression_parameters(1))["content_distance_scale"]
        if (
            config["embedding_profile"] is None
            and changed is not None
            and changed["content_distance_scale"] != base_distance
        ):
            raise _ReadFailure(
                "configuration_invalid",
                "Content comparison is disabled; this override cannot change its threshold.",
            )
        occupied.update(members)
        scopes.append(sorted(members))
    return {
        "profile": profile,
        "configuration": projection,
        "scopes": scopes,
        "input": None
        if inputs is None
        else {
            "result_ref": graph.result_ref,
            "digest": result_digest,
            "members": inputs,
        },
    }


def validate_frozen_preparation(preparation, request):
    """Reject incomplete recovery input; historical Result absence is unrelated."""
    from mediasense.runtime.resources import contract_validator

    if not isinstance(preparation, dict) or set(preparation) != {
        "profile",
        "configuration",
        "scopes",
        "input",
    }:
        raise ValueError("Run frozen preparation is incomplete")
    contract = contract_validator("mediasense.precheck.run")
    validator = contract.evolve(
        schema={"$defs": contract.schema["$defs"], "$ref": "#/$defs/processing_profile"}
    )
    profile = preparation["profile"]
    if not validator.is_valid(profile) or (
        preparation_configuration_identity(preparation["configuration"])
        != profile["configuration_identity"]
    ):
        raise ValueError("Run frozen profile is invalid")
    if "profile" in request and profile != request["profile"]:
        raise ValueError("Run frozen profile contradicts its accepted request")
    snapshot, scopes = preparation["input"], preparation["scopes"]
    if (snapshot is not None) != ("source_set" in request):
        raise ValueError("Run frozen input contradicts its accepted request")
    if not isinstance(scopes, list) or len(scopes) != len(profile["overrides"]):
        raise ValueError("Run frozen scope count disagrees with its profile")
    if snapshot is None:
        if scopes:
            raise ValueError("Run overrides have no frozen input")
        return
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "result_ref",
        "digest",
        "members",
    }:
        raise ValueError("Run frozen input is incomplete")
    if snapshot["result_ref"] != request.get("prior_result_ref") or not isinstance(
        snapshot["members"], list
    ):
        raise ValueError("Run frozen input binding is invalid")
    refs = {member["source_item_ref"] for member in snapshot["members"]}
    if len(refs) != len(snapshot["members"]):
        raise ValueError("Run frozen input has duplicate occurrences")
    occupied = set()
    for scope, override in zip(scopes, profile["overrides"], strict=True):
        selected = set(scope)
        if (
            not selected
            or len(selected) != len(scope)
            or not selected <= refs
            or selected & occupied
        ):
            raise ValueError("Run frozen scope membership is invalid")
        selector = override["source_set"]
        if selector["kind"] == "explicit" and selected != set(
            selector["source_item_refs"]
        ):
            raise ValueError("Run frozen scope contradicts its accepted request")
        occupied.update(selected)


def preparation_readback(result_ref, preparation):
    if preparation is None:
        return None
    profile = deepcopy(preparation["profile"])
    for index, override in enumerate(profile["overrides"]):
        override["source_set"] = {"kind": "profile_scope", "index": index}
    return {
        "source_set": {
            "kind": "precheck_relation",
            "origin": result_ref,
            "relation": "accounts_for",
            "direction": "outbound",
        },
        "profile": profile,
    }


def override_path_partitions(preparation):
    if preparation is None or preparation["input"] is None:
        return {}
    from pathlib import Path

    paths = {
        m["source_item_ref"]: Path(m["locator"]["value"])
        for m in preparation["input"]["members"]
    }
    return {
        paths[ref]: index
        for index, scope in enumerate(preparation["scopes"], start=1)
        for ref in scope
    }


def validate_retained_preparation(
    preparation, bindings, sources, accounts, source_records=None
):
    """Shared publication/read integrity checks, independent of mutable stores."""
    from mediasense.runtime.resources import contract_validator

    if preparation is None:
        if bindings is not None:
            raise ValueError("Input bindings have no retained preparation")
        return
    defs = contract_validator("mediasense.precheck.run").schema["$defs"]
    validator = contract_validator("mediasense.precheck.run").evolve(
        schema={"$defs": defs, "$ref": "#/$defs/processing_profile"}
    )
    if set(preparation) != {
        "profile",
        "configuration",
        "scopes",
    } or not validator.is_valid(preparation["profile"]):
        raise ValueError("Invalid sealed preparation value")
    if (
        preparation_configuration_identity(preparation["configuration"])
        != preparation["profile"]["configuration_identity"]
    ):
        raise ValueError("Sealed configuration identity disagrees with its value")
    scopes = preparation["scopes"]
    if len(scopes) != len(preparation["profile"]["overrides"]):
        raise ValueError("Sealed profile scope count disagrees")
    occupied = set()
    for index, (scope, override) in enumerate(
        zip(scopes, preparation["profile"]["overrides"], strict=True)
    ):
        members = set(scope)
        if (
            not members
            or len(members) != len(scope)
            or members & occupied
            or not members <= sources.keys()
        ):
            raise ValueError("Invalid sealed override membership")
        if any(accounts[ref]["scope"] != "source_media" for ref in scope):
            raise ValueError("Override membership includes non-media")
        if override["source_set"] != {"kind": "profile_scope", "index": index}:
            raise ValueError("Sealed Profile does not address its own membership")
        occupied.update(members)
    if bindings is None:
        if scopes:
            raise ValueError("Overrides have no explicit input bindings")
        return
    if set(bindings) != {"result_ref", "digest", "members"}:
        raise ValueError("Invalid sealed input binding envelope")
    if not isinstance(bindings["result_ref"], str) or not bindings[
        "result_ref"
    ].startswith("precheck-result:"):
        raise ValueError("Invalid bound input Result")
    if not isinstance(bindings["digest"], str) or len(bindings["digest"]) != 64:
        raise ValueError("Invalid bound input digest")
    seen, targets = set(), set()
    for row in bindings["members"]:
        if set(row) != {
            "input_ref",
            "target_ref",
            "locator",
            "verification",
        }:
            raise ValueError("Invalid sealed input binding")
        source, target = row["input_ref"], row["target_ref"]
        if source in seen or target in targets or target not in sources:
            raise ValueError("Contradictory or duplicate sealed input binding")
        seen.add(source)
        targets.add(target)
        if row["locator"] != sources[target]["locator"]:
            raise ValueError("Binding locator disagrees with target occurrence")
        verification = row["verification"]
        if set(verification) != {"status", "profile", "value"} or verification[
            "status"
        ] not in {"verified", "unsupported", "unavailable"}:
            raise ValueError("Invalid retained verification outcome")
        if verification["status"] == "verified":
            from ._fingerprint import FINGERPRINT_ALGORITHM

            if (
                verification["profile"] != FINGERPRINT_ALGORITHM
                or not verification["value"]
            ):
                raise ValueError("Unsupported matched verification")
            if source_records is not None:
                observed = source_records[target].get("accounting")
                if (
                    not observed
                    or row["verification"]["profile"]
                    != observed.get("fingerprint_algorithm")
                    or row["verification"]["value"] != observed.get("fingerprint")
                ):
                    raise ValueError(
                        "Binding verification contradicts the observed target revision"
                    )
    if targets != sources.keys():
        raise ValueError("Input bindings must account for every target occurrence")


def correspondence_for(source_graph, source_digest, target_graph):
    from .read import _ReadFailure

    bindings = target_graph.input_bindings
    if bindings is None:
        code = (
            "input_binding_unrecorded"
            if target_graph.preparation is None
            else "not_direct_successor"
        )
        return lambda ref: {"status": "unproven", "basis": {"code": code}}
    if bindings["result_ref"] != source_graph.result_ref:
        return lambda ref: {
            "status": "unproven",
            "basis": {"code": "not_direct_successor"},
        }
    if getattr(target_graph, "verified_input_digest", None) != source_digest:
        rows = {row["input_ref"]: row for row in bindings["members"]}
        if (
            bindings["digest"] != source_digest
            or rows.keys() != source_graph.sources.keys()
        ):
            raise _ReadFailure(
                "result_inconsistent",
                "Direct input bindings disagree with the original Result.",
            )
        for ref, row in rows.items():
            if row["locator"] != source_graph.sources[ref]["locator"]:
                raise _ReadFailure(
                    "result_inconsistent",
                    "Direct input locator contradicts the original occurrence.",
                )
            if row["verification"]["status"] == "verified":
                original = source_graph.source_records[ref].get("accounting")
                target = target_graph.source_records[row["target_ref"]].get(
                    "accounting"
                )
                if original and (
                    not target
                    or any(
                        original.get(k) != target.get(k)
                        for k in (
                            "fingerprint_algorithm",
                            "fingerprint",
                            "size_bytes",
                            "mtime_ns",
                            "device_id",
                            "inode",
                            "mode",
                        )
                    )
                ):
                    raise _ReadFailure(
                        "result_inconsistent",
                        "Matched input has contradictory revision observations.",
                    )
        target_graph.verified_input_digest = source_digest
        from ._snapshot import binding_correspondence

        target_graph.correspondences = {
            ref: binding_correspondence(row) for ref, row in rows.items()
        }
    return target_graph.correspondences.__getitem__
