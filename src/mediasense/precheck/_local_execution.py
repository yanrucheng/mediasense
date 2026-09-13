"""Project retained Work execution facts; no models or second execution store."""

from copy import deepcopy
import json
import math

from ._work_types import WorkStatus
from .work import WorkStore


class LocalExecutionError(RuntimeError):
    """Committed execution evidence is inconsistent."""


def unrecorded_execution():
    return {
        "status": "not_recorded",
        "resource_budget": None,
        "models": [],
        "batches": [],
    }


def execution_summary(value):
    return {
        key: deepcopy(value[key]) for key in ("status", "resource_budget", "models")
    }


def _totals(batches):
    def total(name):
        values = [b[name] for b in batches]
        return None if any(v is None for v in values) else sum(values)

    return {
        "batch_count": len(batches),
        "input_count": total("input_count"),
        "inference_input_count": total("inference_input_count"),
        "included_work_count": total("included_work_count"),
        "processing_wall_seconds": total("processing_wall_seconds"),
        "load_wall_seconds": total("load_wall_seconds"),
    }


def collect_local_execution(database_path, run_id, config, *, work_ids=None):
    if run_id is None or config is None:
        return unrecorded_execution()
    profiles = config.get("sensitivity_profiles", [])
    identities = config.get("sensitivity_detector_identities", [])
    if len(profiles) != len(identities):
        raise LocalExecutionError("Frozen sensitivity declarations do not correspond")
    models = {}
    for profile, identity in zip(profiles, identities, strict=True):
        models[identity] = {
            "detector_identity": identity,
            "profile": profile["name"],
            "requested_device": profile.get("device"),
            "precision": profile.get("precision"),
            "batch_limit": profile.get("batch_size"),
            "memory_estimate_bytes": profile.get("memory_bytes"),
            "succeeded_work_count": 0,
            "failed_work_count": 0,
            "pending_work_count": 0,
            "unreported_work_count": 0,
        }
    selected = None if work_ids is None else set(work_ids)
    batches = {}
    for record in WorkStore(database_path).iter_run_work(
        run_id, capability="content-sensitivity"
    ):
        if selected is not None and record.work_id not in selected:
            continue
        dependencies = {d.key: d.value for d in record.spec.dependencies}
        identity = dependencies["detector_identity"]
        if identity not in models:
            continue  # Disabled profiles do not enter this Run's requested audit.
        model = models[identity]
        state = (
            "succeeded"
            if record.status is WorkStatus.SUCCEEDED
            else "failed"
            if record.status is WorkStatus.TERMINAL_FAILURE
            else "pending"
        )
        model[state + "_work_count"] += 1
        saved = (record.output or {}).get("execution", {})
        if saved.get("schema_version") != 1 or "batch" not in saved:
            model["unreported_work_count"] += 1
            continue
        batch = deepcopy(saved["batch"])
        origin_run = batch.pop("accounting_run_id")
        batch.update(
            detector_identity=identity,
            profile=model["profile"],
            origin="current" if origin_run == run_id else "reused",
        )
        key = batch["batch_id"]
        prior = batches.get(key)
        if prior is None:
            batches[key] = {"value": batch, "work_ids": {record.work_id}}
        else:
            if prior["value"] != batch:
                raise LocalExecutionError(
                    "One batch identity has contradictory execution facts"
                )
            prior["work_ids"].add(record.work_id)
    rows = []
    for item in batches.values():
        batch = {**item["value"], "included_work_count": len(item["work_ids"])}
        if batch["included_work_count"] > batch["input_count"]:
            raise LocalExecutionError("Batch membership exceeds actual input scope")
        rows.append(batch)
    rows.sort(key=lambda b: (b["observed_at"], b["batch_id"]))
    for identity, model in models.items():
        for origin in ("current", "reused"):
            model["recorded_" + origin] = _totals(
                [
                    b
                    for b in rows
                    if b["detector_identity"] == identity and b["origin"] == origin
                ]
            )
    value = {
        "status": "recorded",
        "resource_budget": deepcopy(config.get("resource_budget")),
        "models": list(models.values()),
        "batches": rows,
    }
    validate_local_execution(value)
    return value


def validate_local_execution(value):
    from mediasense.runtime.resources import contract_validator
    from jsonschema import ValidationError

    validator = contract_validator("mediasense.precheck.run", "status")
    schema = {"$defs": validator.schema["$defs"], "$ref": "#/$defs/local_execution"}
    try:
        validator.evolve(schema=schema).validate(
            {**value, "page": {"total": len(value["batches"]), "next_cursor": None}}
        )
        json.dumps(value, allow_nan=False)
        if set(value) != {"status", "resource_budget", "models", "batches"}:
            raise ValueError("Unknown local execution fields")
        if value["status"] == "not_recorded" and value != unrecorded_execution():
            raise ValueError("Unrecorded execution cannot fabricate facts")
        models = {m["detector_identity"]: m for m in value["models"]}
        if len(models) != len(value["models"]):
            raise ValueError("Duplicate execution model")
        seen = set()
        for batch in value["batches"]:
            if batch["batch_id"] in seen:
                raise ValueError("Duplicate execution batch")
            seen.add(batch["batch_id"])
            if (
                batch["detector_identity"] not in models
                or models[batch["detector_identity"]]["profile"] != batch["profile"]
            ):
                raise ValueError("Execution batch is outside the frozen profile")
            if batch["included_work_count"] > batch["input_count"] or (
                batch["inference_input_count"] is not None
                and batch["inference_input_count"] > batch["input_count"]
            ):
                raise ValueError("Invalid execution batch scope")
        for identity, model in models.items():
            linked_work = sum(
                b["included_work_count"]
                for b in value["batches"]
                if b["detector_identity"] == identity
            )
            if linked_work + model["unreported_work_count"] != sum(
                model[k]
                for k in (
                    "succeeded_work_count",
                    "failed_work_count",
                    "pending_work_count",
                )
            ):
                raise ValueError(
                    "Execution batch coverage disagrees with Work accounting"
                )
            for origin in ("current", "reused"):
                actual = _totals(
                    [
                        b
                        for b in value["batches"]
                        if b["detector_identity"] == identity and b["origin"] == origin
                    ]
                )
                for name, expected in actual.items():
                    observed = model["recorded_" + origin][name]
                    if (expected is None or observed is None) and expected != observed:
                        raise ValueError("Unknown execution total was fabricated")
                    if (
                        expected is not None
                        and observed is not None
                        and not math.isclose(
                            expected, observed, rel_tol=0, abs_tol=1e-9
                        )
                    ):
                        raise ValueError("Execution totals contradict unique batches")
    except (ValidationError, ValueError, TypeError, KeyError) as error:
        raise LocalExecutionError(str(error)) from error
