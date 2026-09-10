"""PreCheck projection of an explicitly confirmed Geo recovery."""

from dataclasses import replace
from datetime import datetime, timedelta
import json

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoEffectEnvelope,
    GeoSubject,
    GeoCoordinate,
    GeoRequest,
    GeoOperation,
    GeoRetention,
    GeoRouteContext,
)
from mediasense.capabilities.geo.tool import result_digest, _parse_request

from ._work_types import DependencyKind, WorkDependency, WorkStatus


def recover(
    producer, public_run_ref, run_id, batch, profile, owner, *, retained_request_id=None
):
    from .geocode import (
        ReverseGeocodeBatchOutcome,
        _geo_authorization,
        _tool_request_id,
    )

    geo = producer.geo_tool
    if geo is None:
        return ReverseGeocodeBatchOutcome("unavailable", batch, (), 0)
    blocked = next(
        (
            r
            for r in batch.work
            if isinstance(r.output, dict)
            and (
                r.output.get("geo_blocked")
                or r.output.get("result", {}).get("status") == "indeterminate"
            )
        ),
        None,
    )
    if retained_request_id is not None:
        retained_cycle = geo.journal.cycle(retained_request_id)
        proof = json.loads(retained_cycle["authority_json"])["precheck_confirmation"]
        original_id = retained_request_id
    else:
        proof = blocked.output["authorization"]
        original_id = blocked.output.get("geo_request_id") or _tool_request_id(
            proof["run_ref"], proof["pending_fingerprint"]
        )
    prior = geo.journal.latest(original_id)
    if prior is None:
        return producer._collect(batch, actual_provider_requests=0)
    cycle = geo.journal.cycle(prior.request_id)
    if cycle is None and prior.state != "completed":
        return producer._collect(batch, actual_provider_requests=0)
    if cycle is None:
        # Legacy completed batches retain every original subject and coordinate.
        # Reconstruct the old request and verify its original authority binding.
        subjects = {}
        for c in prior.result["components"]:
            for ref in c["subject_refs"]:
                subjects[ref] = GeoSubject(ref, GeoCoordinate(**c["coordinate"]))
        value = GeoRequest(
            GeoOperation.RESOLVE_PLACE,
            tuple(subjects.values()),
            "zh",
            radius_meters=profile.nearby_radius_meters,
            max_places=profile.max_places,
            retention=GeoRetention.CALLER_STATE,
            route_context=GeoRouteContext(locale="zh"),
        )
        old_authority = _legacy_authority(value, proof, prior)
        geo.journal.adopt_legacy(
            prior.request_id, value.value(), old_authority, confirmation_proof=proof
        )
        cycle = geo.journal.cycle(prior.request_id)
    value = _parse_request(json.loads(cycle["request_json"]))
    if not cycle["closed"]:
        # Reconcile the prior cycle using its retained scope, not today's network
        # settings. This phase is entirely local and cannot reset its budget.
        with geo.journal.ownership(prior.request_id) as owned:
            if not owned:
                return producer._collect(batch, actual_provider_requests=0)
            from mediasense.capabilities.geo._checkpoint import reconcile

            response = reconcile(geo.journal, prior, value)
            geo.journal.complete(prior.request_id, response)
            prior = geo.journal.get(prior.request_id)
            cycle = geo.journal.cycle(prior.request_id)
    original_subjects = {s.coordinate: s.subject_ref for s in value.subjects}
    request = {
        **value.value(),
        "request_id": _tool_request_id(
            public_run_ref,
            result_digest(
                {
                    "prior": prior.request_id,
                    "result": result_digest(prior.result),
                }
            ),
        ),
        "recovery": {
            "prior_request_id": prior.request_id,
            "result_digest": result_digest(prior.result),
        },
    }
    # A completed successor may exist even though its Work projection never ran.
    # Deliver that exact response before proposing any further remote execution.
    proposal = (
        prior.result
        if retained_request_id is not None or prior.request_id != original_id
        else geo.handle(request)
    )
    if proposal.get("error", {}).get("code") == "recovery_unavailable":
        return producer._collect(batch, actual_provider_requests=0)
    if proposal.get("outcome") == "error":
        raise RuntimeError(f"Geo recovery rejected: {proposal['error']['code']}")
    if proposal.get("outcome") == "unavailable":
        return ReverseGeocodeBatchOutcome("unavailable", batch, (), 0)
    fingerprint = proposal["request_fingerprint"]
    if proposal.get("outcome") == "authorization_required":
        envelope = GeoEffectEnvelope(**proposal["required_authorization"])
        disclosure = producer._disclosure(proposal, batch=batch, profile=profile)
        from mediasense.capabilities.geo.service import remaining_request

        missing_scope = remaining_request(value, prior.result)
        pending_components = [
            {"coordinate": c["coordinate"], "operation": c["operation"]}
            for c in prior.result["components"]
            if c["status"] not in {"success", "no_result"}
        ]
        disclosure.update(
            geo_request_fingerprint=fingerprint,
            coordinates=[s.coordinate.value() for s in missing_scope.subjects],
            pending_logical_queries=missing_scope.logical_query_count,
            original_logical_queries=value.logical_query_count,
            pending_components=pending_components,
            recovery_of=prior.request_id,
            recovery_accounting=proposal.get("recovery"),
            prior_provider_requests=prior.result["effects"]["provider_requests"],
            prior_billable_units=prior.result["effects"]["billable_units"],
            cumulative_provider_request_ceiling=envelope.max_provider_requests,
            recovery_policy="Retain successful components; retry only missing evidence under the original cumulative ceiling. Prior unknown effects and charges remain unknown.",
        )
        status = producer.run_tool.require_confirmation(
            public_run_ref,
            summary="Recover missing Geo evidence after resolving the reported network or provider condition.",
            quantity=missing_scope.logical_query_count,
            unit="logical_queries",
            skip_allowed=False,
            pending_fingerprint=fingerprint,
            disclosure=disclosure,
        )
        if status["state"] == "paused":
            return ReverseGeocodeBatchOutcome("confirmation_required", batch, (), 0)
        authority = producer.run_tool.confirmation_authority(
            public_run_ref,
            pending_fingerprint=fingerprint,
        )
        if authority is None:
            raise RuntimeError("Geo recovery requires exact trusted confirmation")
        response = geo.handle(
            request,
            authorization=_geo_authorization(authority, fingerprint, proposal),
            confirmation_proof={
                **authority,
                "run_ref": public_run_ref,
                "pending_fingerprint": fingerprint,
                "confirmed_logical_queries": missing_scope.logical_query_count,
                "decision": "proceed",
                "disclosure_identity": authority["confirmed_content_identity"],
            },
            cancelled=lambda: (
                producer.run_tool.current_state(public_run_ref) != "running"
            ),
        )
    else:
        response = proposal
        authority = producer.run_tool.confirmation_authority(
            public_run_ref, pending_fingerprint=fingerprint
        )
        if authority is None:
            # The persisted completed recovery proves its accepted authority.
            recovered_cycle = geo.journal.cycle(response["request_id"])
            accepted = json.loads(recovered_cycle["authority_json"])
            authority = accepted.get("precheck_confirmation")
            if authority is None:
                raise RuntimeError(
                    "Persisted recovery lacks its exact PreCheck confirmation proof"
                )
    if response.get("outcome") in {"error", "authorization_required", "unavailable"}:
        return producer._collect(batch, actual_provider_requests=0)
    records, pending, remap = [], [], {}
    retired = []
    for query, record in zip(batch.queries, batch.work, strict=True):
        subject = original_subjects.get(query.coordinate)
        needs = record.status is not WorkStatus.SUCCEEDED or (
            record.output
            and (
                record.output.get("geo_blocked")
                or record.output.get("result", {}).get("status") == "indeterminate"
            )
        )
        if subject is not None and needs:
            spec = replace(
                record.spec,
                dependencies=tuple(
                    d
                    for d in record.spec.dependencies
                    if d.key != "geo_recovery_result"
                )
                + (
                    WorkDependency(
                        DependencyKind.PARAMETER,
                        "geo_recovery_result",
                        result_digest(response),
                    ),
                ),
            )
            successor = producer.work.ensure_work(
                run_id, spec, max_attempts=profile.max_attempts
            )
            retired.append(record.work_id)
            remap[subject] = successor.work_id
            record = successor
            if record.status is not WorkStatus.SUCCEEDED:
                pending.append((query, record))
        records.append(record)
    updated = replace(batch, work=tuple(records), pending_fingerprint=fingerprint)
    projected = {
        **response,
        "components": [
            {**c, "subject_refs": [remap.get(ref, ref) for ref in c["subject_refs"]]}
            for c in response["components"]
        ],
    }
    leases = producer._claim_pending(run_id, pending, owner)
    if len(leases) != len(pending):
        raise RuntimeError("Geo recovery projection could not claim all selected Work")
    try:
        producer._persist_response(
            public_run_ref, updated, pending, leases, projected, authority, profile
        )
    except Exception:
        for lease in leases.values():
            if producer.work.get_work(lease.work_id).status is WorkStatus.RUNNING:
                producer.work.fail_work(
                    lease,
                    error_code="geo_projection_failed",
                    message="Persisted Geo response needs local projection; no new provider request is needed.",
                    retryable=True,
                    retry_delay=timedelta(0),
                )
        raise
    producer.work.detach_run_work(run_id, retired)
    current_count = response["effects"]["provider_requests"]
    prior_count = prior.result["effects"]["provider_requests"]
    return producer._collect(
        updated,
        actual_provider_requests=(
            max(0, current_count - prior_count)
            if current_count is not None and prior_count is not None
            else None
        ),
    )


def _legacy_authority(value, proof, prior):
    """Recognize the released 0.9 grant by exact binding, never today's routing."""
    from mediasense.capabilities.geo.model import RetryPolicy
    import hashlib

    old_fingerprint = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                {"request": value.fingerprint(), "retry_policy": RetryPolicy().value()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    if old_fingerprint != prior.request_fingerprint:
        raise ValueError(
            "Retained legacy Geo request does not prove the released 0.9 profile"
        )
    for providers in (("google_maps", "amap"), ("google_maps",), ("amap",)):
        envelope = GeoEffectEnvelope(
            providers,
            value.logical_query_count,
            value.logical_query_count
            * 3
            * sum(
                2 if p == "google_maps" and value.expands_nearby else 1
                for p in providers
            ),
            allow_unknown_billable_units=True,
            retention=value.retention,
        )
        authority = GeoAuthorization(
            proof["principal_ref"],
            prior.request_fingerprint,
            datetime.fromisoformat(proof["confirmed_at"]),
            envelope,
        )
        if authority.binding() == prior.authorization_binding:
            return authority
    raise ValueError("Retained legacy Geo authorization binding is not reconstructible")


def reclaim_projection_leases(producer, run_id):
    """Called only while holding this Run's OS Geo production lock.

    v2 owners hold that lock until Work projection finishes. Acquiring it proves
    an unfinished v2 lease has no live owner; legacy leases retain their TTL.
    """
    from ._work_types import WorkLease

    producer.work.recover_expired_leases()
    for record in producer.work.iter_run_work(
        run_id, capability="reverse-geocode-observation"
    ):
        if (
            record.status is WorkStatus.RUNNING
            and record.lease_run_id == run_id
            and record.lease_owner.startswith("geo-projection-v2:")
        ):
            attempt = producer.work.get_attempts(record.work_id)[-1]
            lease = WorkLease(
                record.work_id,
                run_id,
                attempt.lease_owner,
                attempt.lease_token,
                attempt.attempt_number,
                attempt.lease_expires_at,
            )
            producer.work.fail_work(
                lease,
                error_code="geo_projection_interrupted",
                message="The Geo production owner stopped before local projection committed; retained responses will be replayed without new HTTP.",
                retryable=True,
                retry_delay=timedelta(0),
            )
