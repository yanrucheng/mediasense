from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCandidate,
    GeoCandidateKind,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoOperation,
    GeoOperationJournal,
    GeoProviderAttempt,
    GeoProviderCapabilities,
    GeoProviderExecution,
    GeoQueryTool,
    MapDatum,
    OrderedGeoRoutingPolicy,
)
from mediasense.capabilities.geo.service import GeoCapability


@dataclass
class FakeProvider:
    capabilities: GeoProviderCapabilities
    calls: int = 0
    fail_after_effect: bool = False

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
    ) -> GeoProviderExecution:
        self.calls += 1
        if self.fail_after_effect:
            raise RuntimeError("lost provider response")
        if operation is GeoOperation.RESOLVE_PLACE:
            return GeoProviderExecution(
                GeoComponentResult(
                    GeoOperation.REVERSE_GEOCODE,
                    GeoComponentStatus.SUCCESS,
                    (),
                    coordinate,
                    (
                        GeoCandidate(
                            GeoCandidateKind.ADDRESS,
                            "Shanghai Disneyland",
                            coordinate=coordinate,
                        ),
                    ),
                ),
                GeoProviderAttempt(
                    self.capabilities.provider_id,
                    GeoOperation.REVERSE_GEOCODE,
                    GeoComponentStatus.SUCCESS,
                    coordinate,
                    coordinate,
                    1,
                    None,
                ),
                (
                    GeoComponentResult(
                        GeoOperation.NEARBY_PLACES,
                        GeoComponentStatus.SUCCESS,
                        (),
                        coordinate,
                        (
                            GeoCandidate(
                                GeoCandidateKind.PLACE,
                                "Toy Story Hotel",
                                coordinate=coordinate,
                            ),
                        ),
                    ),
                ),
                (
                    GeoProviderAttempt(
                        self.capabilities.provider_id,
                        GeoOperation.NEARBY_PLACES,
                        GeoComponentStatus.SUCCESS,
                        coordinate,
                        coordinate,
                        1,
                        None,
                    ),
                ),
            )
        kind = (
            GeoCandidateKind.PLACE
            if operation is GeoOperation.NEARBY_PLACES
            else GeoCandidateKind.ADDRESS
        )
        return GeoProviderExecution(
            GeoComponentResult(
                operation,
                GeoComponentStatus.SUCCESS,
                (),
                coordinate,
                (GeoCandidate(kind, "Shanghai Disneyland", coordinate=coordinate),),
            ),
            GeoProviderAttempt(
                self.capabilities.provider_id,
                operation,
                GeoComponentStatus.SUCCESS,
                coordinate,
                coordinate,
                1,
                1,
            ),
        )


def _tool(tmp_path: Path, *, fail_after_effect: bool = False) -> tuple[GeoQueryTool, FakeProvider]:
    provider = FakeProvider(
        GeoProviderCapabilities(
            "provider-a",
            (
                GeoOperation.RESOLVE_PLACE,
                GeoOperation.REVERSE_GEOCODE,
                GeoOperation.NEARBY_PLACES,
            ),
            MapDatum.WGS84,
            operation_request_ceilings=((GeoOperation.RESOLVE_PLACE, 2),),
        ),
        fail_after_effect=fail_after_effect,
    )
    capability = GeoCapability(
        {"provider-a": provider}, OrderedGeoRoutingPolicy(("provider-a",))
    )
    return (
        GeoQueryTool(capability, GeoOperationJournal(tmp_path / "geo.sqlite3")),
        provider,
    )


def _contract() -> dict[str, object]:
    path = (
        Path(__file__).parents[1]
        / "docs"
        / "spec"
        / "spec-260830-2034-geo-query"
        / "geo-query.tool.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _mock() -> dict[str, object]:
    path = (
        Path(__file__).parents[1]
        / "docs"
        / "spec"
        / "spec-260830-2034-geo-query"
        / "geo-query.mock.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _request(operation: str = "resolve_place") -> dict[str, object]:
    value: dict[str, object] = {
        "request_id": "request:geo-one",
        "operation": operation,
        "subjects": [
            {
                "subject_ref": "source-item:one",
                "coordinate": {
                    "latitude": 31.1434,
                    "longitude": 121.6579,
                    "datum": "WGS84",
                },
            }
        ],
        "locale": "zh-CN",
        "retention": "caller_state",
    }
    if operation == "nearby_places":
        value["radius_meters"] = 500
        value["max_places"] = 10
    return value


def _expanded_request() -> dict[str, object]:
    return {
        **_request(),
        "radius_meters": 500,
        "max_places": 10,
    }


def _authorization(tool: GeoQueryTool, request: dict[str, object]) -> GeoAuthorization:
    from mediasense.capabilities.geo.tool import _parse_request

    parsed = _parse_request(request)
    return GeoAuthorization(
        "human:one",
        parsed.fingerprint(),
        datetime.now(timezone.utc),
        tool.capability.proposed_envelope(parsed),
    )


def test_tool_preflight_is_effect_free_and_describes_authorization(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)

    result = tool.handle(_request())

    assert result["outcome"] == "authorization_required"
    assert result["required_authorization"]["max_logical_queries"] == 1
    assert result["effects"]["provider_requests"] == 0
    assert provider.calls == 0

    expanded = tool.handle(_expanded_request())
    assert expanded["outcome"] == "authorization_required"
    assert expanded["required_authorization"]["max_provider_requests"] == 2
    assert expanded["effects"]["provider_requests"] == 0
    assert provider.calls == 0


def test_tool_contract_accepts_request_preflight_and_success(tmp_path: Path) -> None:
    tool, _provider = _tool(tmp_path)
    request = _request()
    contract = _contract()
    input_validator = Draft202012Validator(contract["inputSchema"])
    output_validator = Draft202012Validator(contract["outputSchema"])

    input_validator.validate(request)
    output_validator.validate(tool.handle(request))
    output_validator.validate(
        tool.handle(request, authorization=_authorization(tool, request))
    )
    expanded = _expanded_request()
    expanded["request_id"] = "request:geo-expanded"
    input_validator.validate(expanded)
    output_validator.validate(tool.handle(expanded))
    output_validator.validate(
        tool.handle(expanded, authorization=_authorization(tool, expanded))
    )


def test_geo_reference_outputs_conform_to_contract() -> None:
    output_validator = Draft202012Validator(_contract()["outputSchema"])

    for key, value in _mock().items():
        if key in {"authorization_required", "authorization_mismatch", "success", "partial_result"}:
            output_validator.validate(value)


def test_contract_valid_requests_are_runtime_valid(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    input_validator = Draft202012Validator(_contract()["inputSchema"])
    repeated_subject = _request()
    repeated_subject["subjects"].append(
        {
            "subject_ref": "source-item:one",
            "coordinate": {
                "latitude": 31.144,
                "longitude": 121.658,
                "datum": "WGS84",
            },
        }
    )
    requests = [
        _request(),
        _request("reverse_geocode"),
        _request("nearby_places"),
        _expanded_request(),
        repeated_subject,
    ]

    for index, request in enumerate(requests):
        request["request_id"] = f"request:conformance-{index}"
        input_validator.validate(request)
        response = tool.handle(request)
        assert response["outcome"] == "authorization_required"

    assert provider.calls == 0


def test_contract_invalid_requests_are_not_silently_accepted(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    input_validator = Draft202012Validator(_contract()["inputSchema"])
    invalid_requests = []
    missing_datum = _request()
    del missing_datum["subjects"][0]["coordinate"]["datum"]
    invalid_requests.append(missing_datum)
    whitespace_subject = _request()
    whitespace_subject["subjects"][0]["subject_ref"] = "   "
    invalid_requests.append(whitespace_subject)
    whitespace_locale = _request()
    whitespace_locale["locale"] = " \t "
    invalid_requests.append(whitespace_locale)
    incomplete_expansion = _request()
    incomplete_expansion["radius_meters"] = 500
    invalid_requests.append(incomplete_expansion)

    for request in invalid_requests:
        assert list(input_validator.iter_errors(request))
        response = tool.handle(request)
        assert response["outcome"] == "error"
        assert response["error"]["code"] == "invalid_request"

    assert provider.calls == 0


def test_all_public_outcomes_conform_to_output_schema(tmp_path: Path) -> None:
    tool, _provider = _tool(tmp_path)
    output_validator = Draft202012Validator(_contract()["outputSchema"])
    request = _request()
    output_validator.validate(tool.handle(request))
    output_validator.validate(
        tool.handle(request, authorization=_authorization(tool, request))
    )
    invalid = {**request, "source_path": "/private/photos/secret.jpg"}
    output_validator.validate(tool.handle(invalid))


def test_tool_replays_terminal_result_without_repeating_provider_effect(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    request = _request()
    authorization = _authorization(tool, request)

    first = tool.handle(request, authorization=authorization)
    restarted_tool, restarted_provider = _tool(tmp_path)
    replay = restarted_tool.handle(request, authorization=authorization)

    assert first == replay
    assert first["outcome"] == "success"
    assert provider.calls == 1
    assert restarted_provider.calls == 0


def test_tool_replays_expanded_resolve_without_repeating_either_effect(
    tmp_path: Path,
) -> None:
    tool, provider = _tool(tmp_path)
    request = _expanded_request()
    authorization = _authorization(tool, request)

    first = tool.handle(request, authorization=authorization)
    restarted_tool, restarted_provider = _tool(tmp_path)
    replay = restarted_tool.handle(request, authorization=authorization)

    assert first == replay
    assert first["outcome"] == "success"
    assert [component["operation"] for component in first["components"]] == [
        "reverse_geocode",
        "nearby_places",
    ]
    assert first["effects"]["provider_requests"] == 2
    assert provider.calls == 1
    assert restarted_provider.calls == 0


def test_tool_replays_same_request_without_reauthorizing_provider_effect(
    tmp_path: Path,
) -> None:
    tool, provider = _tool(tmp_path)
    request = _request()
    authorization = _authorization(tool, request)
    first = tool.handle(request, authorization=authorization)

    replay = tool.handle(request)

    assert replay == first
    assert provider.calls == 1


def test_tool_rejects_request_id_reuse_with_changed_authority(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    request = _request()
    authorization = _authorization(tool, request)
    assert tool.handle(request, authorization=authorization)["outcome"] == "success"
    changed = GeoAuthorization(
        "human:two",
        authorization.request_fingerprint,
        authorization.authorized_at,
        authorization.envelope,
    )

    conflict = tool.handle(request, authorization=changed)

    assert conflict["outcome"] == "error"
    assert conflict["error"]["code"] == "idempotency_conflict"
    assert provider.calls == 1


def test_tool_keeps_interrupted_effect_indeterminate_on_retry(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path, fail_after_effect=True)
    request = _expanded_request()
    authorization = _authorization(tool, request)

    first = tool.handle(request, authorization=authorization)
    replay = tool.handle(request, authorization=authorization)

    assert first == replay
    assert first["outcome"] == "indeterminate"
    assert first["effects"]["provider_requests"] is None
    assert [component["operation"] for component in first["components"]] == [
        "reverse_geocode",
        "nearby_places",
    ]
    assert provider.calls == 1


def test_tool_cancellation_prevents_new_provider_effect(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    request = _request()
    authorization = _authorization(tool, request)

    result = tool.handle(
        request,
        authorization=authorization,
        cancelled=lambda: True,
    )

    assert result["outcome"] == "cancelled"
    assert result["effects"]["provider_requests"] == 0
    assert result["components"][0]["status"] == "not_requested"
    assert provider.calls == 0


def test_tool_refuses_uncontracted_context_before_provider_effect(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    request = {**_request(), "source_path": "/private/photos/secret.jpg"}

    result = tool.handle(request)

    assert result["outcome"] == "error"
    assert result["error"]["code"] == "invalid_request"
    assert provider.calls == 0


def test_nearby_continuation_requires_its_own_request_identity(tmp_path: Path) -> None:
    tool, provider = _tool(tmp_path)
    resolved = _request()
    resolved_authorization = _authorization(tool, resolved)
    assert tool.handle(resolved, authorization=resolved_authorization)["outcome"] == "success"

    nearby = _request("nearby_places")
    stale = tool.handle(nearby, authorization=resolved_authorization)
    assert stale["outcome"] == "error"
    assert stale["error"]["code"] == "idempotency_conflict"
    assert provider.calls == 1

    nearby_authorization = _authorization(tool, nearby)
    nearby["request_id"] = "request:geo-nearby"
    accepted = tool.handle(nearby, authorization=nearby_authorization)
    assert accepted["outcome"] == "success"
    assert provider.calls == 2
