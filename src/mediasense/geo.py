"""Shared address and nearby-place primitives used by stage-neutral Geo queries."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
import socket
import ssl
import http.client
from threading import Lock
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    Request,
    urlopen,
    build_opener,
    ProxyHandler,
    HTTPSHandler,
    getproxies,
)
from urllib.parse import urlsplit
import hashlib
import os

from .capabilities.geo.model import (
    GeoCandidate,
    GeoCandidateKind,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoLookupError,
    GeoLookupResult,
    GeoOperation,
    GeoPermanentError,
    GeoProviderAttempt,
    GeoProviderResult,
    GeoTransientError,
    MapDatum,
)
from .capabilities.geo.protocol import (
    GeoProviderCapabilities,
    GeoProviderExecution,
    ReverseGeocodeProvider,
)


def _http_timeout(
    timeout: float, deadline: float | None, cancelled: Callable[[], bool] | None
) -> float:
    if cancelled is not None and cancelled():
        raise GeoPermanentError("Geo request cancelled before HTTP admission.")
    remaining = (
        timeout if deadline is None else min(timeout, deadline - time.monotonic())
    )
    if remaining <= 0:
        raise GeoPermanentError(
            "Geo coordinate deadline exhausted before HTTP admission."
        )
    return remaining


class JsonTransport(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, object],
        headers: Mapping[str, str] | None,
        timeout: float,
    ) -> Mapping[str, object]: ...

    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, object],
        headers: Mapping[str, str] | None,
        timeout: float,
    ) -> Mapping[str, object]: ...


class CoordinateConverter(Protocol):
    def convert(self, coordinate: GeoCoordinate, target: MapDatum) -> GeoCoordinate: ...


class XYConvertCoordinateConverter:
    """Scalar port characterized against AI Album's ``xyconvert==0.1.2``."""

    def convert(self, coordinate: GeoCoordinate, target: MapDatum) -> GeoCoordinate:
        target = MapDatum(target)
        if coordinate.datum is target:
            return coordinate
        if coordinate.datum is MapDatum.WGS84 and target is MapDatum.GCJ02:
            longitude, latitude = _wgs84_to_gcj02(
                coordinate.longitude, coordinate.latitude
            )
        elif coordinate.datum is MapDatum.GCJ02 and target is MapDatum.WGS84:
            longitude, latitude = _gcj02_to_wgs84(
                coordinate.longitude, coordinate.latitude
            )
        else:
            raise GeoPermanentError(
                f"unsupported datum conversion: {coordinate.datum} to {target}"
            )
        return GeoCoordinate(
            latitude=latitude,
            longitude=longitude,
            datum=target,
        )


class UrllibJsonTransport:
    """Small explicit HTTP adapter; constructing providers never sends a request."""

    def __init__(
        self,
        *,
        proxy_url: str | None = None,
        ca_bundle: str | None = None,
        configured: bool = False,
    ):
        self._opener = None
        self.network_profile = None
        if not configured and proxy_url is None and ca_bundle is None:
            return
        proxies = getproxies()
        if "all" in proxies:
            proxies.setdefault("http", proxies["all"])
            proxies.setdefault("https", proxies["all"])
        if proxy_url is not None:
            proxies["http"] = proxies["https"] = proxy_url
        for value in (proxies.get("http"), proxies.get("https")):
            if value and urlsplit(value).scheme not in {"http", "https"}:
                raise ValueError(
                    "Geo supports HTTP/HTTPS proxies; configure an HTTP tunnel for other proxy protocols."
                )
        bundle = (
            ca_bundle
            or os.environ.get("SSL_CERT_FILE")
            or os.environ.get("REQUESTS_CA_BUNDLE")
            or os.environ.get("CURL_CA_BUNDLE")
        )
        context = ssl.create_default_context(cafile=bundle)
        self._opener = build_opener(
            ProxyHandler(proxies), HTTPSHandler(context=context)
        )
        from pathlib import Path

        effective = {
            "proxies": proxies,
            "ca_digest": hashlib.sha256(Path(bundle).read_bytes()).hexdigest()
            if bundle
            else "system",
        }
        identity = (
            "sha256:"
            + hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
        )
        recipients = []
        for value in (proxies.get("http"), proxies.get("https")):
            if value:
                parsed = urlsplit(value)
                recipient = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}"
                if recipient not in recipients:
                    recipients.append(recipient)
        self.network_profile = {
            "identity": identity,
            "proxy_receivers": recipients,
            "no_proxy_configured": bool(proxies.get("no")),
            "ca_source": "configured_bundle" if bundle else "system",
            "reachability": "not_checked",
            "tls_verification": True,
        }

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
        timeout: float,
    ) -> Mapping[str, object]:
        query = urlencode({key: str(value) for key, value in params.items()})
        request = Request(f"{url}?{query}", headers=dict(headers or {}))
        return self._open(request, timeout)

    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
        timeout: float,
    ) -> Mapping[str, object]:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=encoded,
            headers={"Content-Type": "application/json", **dict(headers or {})},
            method="POST",
        )
        return self._open(request, timeout)

    def _open(self, request: Request, timeout: float) -> Mapping[str, object]:
        try:
            opener = self._opener.open if self._opener is not None else urlopen
            with opener(request, timeout=timeout) as response:  # noqa: S310
                value = json.loads(response.read())
        except HTTPError as error:
            if error.code in {408, 425, 429} or error.code >= 500:
                raise _HttpTransientResponseError(error) from error
            raise _HttpResponseError(error) from error
        except (OSError, URLError, http.client.HTTPException) as error:
            cause = error.reason if isinstance(error, URLError) else error
            if isinstance(cause, ssl.SSLCertVerificationError):
                raise GeoPermanentError(
                    "TLS certificate verification failed before the application request.",
                    failure_code="tls_certificate",
                ) from error
            unsent = isinstance(error, URLError) and isinstance(
                error.reason, (ConnectionRefusedError, socket.gaierror)
            )
            category = (
                "dns_failure"
                if unsent and isinstance(cause, socket.gaierror)
                else "connection_refused"
                if unsent
                else "transport_timeout"
                if isinstance(cause, TimeoutError)
                else "tls_failure"
                if isinstance(cause, ssl.SSLError)
                else "connection_lost"
                if isinstance(cause, (ConnectionError, http.client.HTTPException))
                else "transport_unknown"
            )
            raise GeoTransientError(
                f"Geo transport {category}; "
                + (
                    "application request was not sent."
                    if unsent
                    else "application request completion is unknown."
                ),
                request_count=0 if unsent else 1,
                safe_to_retry=unsent,
                failure_code=category,
            ) from error
        except (UnicodeError, json.JSONDecodeError) as error:
            raise GeoPermanentError(
                "provider response is not valid JSON",
                request_count=1,
                failure_code="provider_response_invalid",
            ) from error
        if not isinstance(value, Mapping):
            raise GeoPermanentError(
                "provider response must be a JSON object",
                request_count=1,
                failure_code="provider_response_invalid",
            )
        return value


class _HttpResponseError(GeoPermanentError):
    """Bounded response detail for adapter classification, never raw diagnostics."""

    def __init__(self, error: HTTPError) -> None:
        self.http_status = error.code
        self.response = _read_http_error_response(error)
        super().__init__(
            f"provider HTTP {error.code}",
            request_count=1,
            failure_code="authentication"
            if error.code in {401, 403, 407}
            else "provider_http_rejected",
            retry_after=_http_retry_after(error),
        )


class _HttpTransientResponseError(GeoTransientError):
    """HTTP retry fallback retaining detail for a more specific adapter verdict."""

    def __init__(self, error: HTTPError) -> None:
        self.http_status = error.code
        retry_after = _http_retry_after(error)
        self.response = _read_http_error_response(error)
        super().__init__(
            f"provider HTTP {error.code}",
            request_count=1,
            safe_to_retry=True,
            failure_code="rate_limited" if error.code == 429 else "service_transient",
            retry_after=retry_after,
        )


def _http_retry_after(error: HTTPError) -> float | None:
    raw_delay = error.headers.get("Retry-After") if error.headers else None
    return min(float(raw_delay), 86400) if raw_delay and raw_delay.isdecimal() else None


def _read_http_error_response(error: HTTPError) -> Mapping[str, object]:
    try:
        # The adapter may refine HTTP fallbacks, including 429/5xx. Raw message,
        # metadata and URLs stay in memory and never enter retained diagnostics.
        value = json.loads(error.read(65536))
    except (OSError, UnicodeError, ValueError):
        value = {}
    finally:
        error.close()
    return value if isinstance(value, Mapping) else {}


def _google_error_signals(value: object) -> tuple[str | None, tuple[str, ...]]:
    error = value.get("error") if isinstance(value, Mapping) else None
    if not isinstance(error, Mapping):
        return None, ()
    status = error.get("status")
    status = (
        status
        if status
        in (
            "INVALID_ARGUMENT",
            "FAILED_PRECONDITION",
            "PERMISSION_DENIED",
            "UNAUTHENTICATED",
            "RESOURCE_EXHAUSTED",
            "INTERNAL",
            "UNAVAILABLE",
        )
        else None
    )
    details = error.get("details")
    reasons = tuple(
        item["reason"]
        for item in (details if isinstance(details, list) else ())
        if isinstance(item, Mapping)
        and item.get("@type") == "type.googleapis.com/google.rpc.ErrorInfo"
        and item.get("domain") == "googleapis.com"
        and item.get("reason")
        in (
            "SERVICE_DISABLED",
            "BILLING_DISABLED",
            "API_KEY_INVALID",
            "API_KEY_EXPIRED",
            "API_KEY_SERVICE_BLOCKED",
            "API_KEY_HTTP_REFERRER_BLOCKED",
            "API_KEY_IP_ADDRESS_BLOCKED",
            "CONSUMER_INVALID",
            "RATE_LIMIT_EXCEEDED",
            "QUOTA_EXCEEDED",
        )
    )
    return status, reasons


def _google_response_error(
    status: str | None,
    reasons: tuple[str, ...],
    *,
    fallback: str = "provider_http_rejected",
    http_status: int | None = None,
    retry_after: float | None = None,
) -> GeoLookupError:
    if any(
        reason in {"SERVICE_DISABLED", "BILLING_DISABLED", "CONSUMER_INVALID"}
        for reason in reasons
    ):
        code = "provider_configuration"
    elif any(reason.startswith("API_KEY_") for reason in reasons) or status in {
        "PERMISSION_DENIED",
        "UNAUTHENTICATED",
    }:
        code = "authentication"
    elif "QUOTA_EXCEEDED" in reasons:
        code = "provider_quota"
    elif "RATE_LIMIT_EXCEEDED" in reasons:
        code = "rate_limited"
    elif status == "RESOURCE_EXHAUSTED":
        code = "rate_limited" if http_status == 429 else "provider_quota"
    elif status in {"INTERNAL", "UNAVAILABLE"}:
        code = "service_transient"
    elif status == "FAILED_PRECONDITION":
        code = "provider_configuration"
    elif status == "INVALID_ARGUMENT":
        code = "provider_request_invalid"
    else:
        code = fallback
    transient = code in {"rate_limited", "service_transient"}
    error_type = GeoTransientError if transient else GeoPermanentError
    return error_type(
        f"Google request rejected: {code}; HTTP={http_status or 'not_reported'}; status={status or 'unclassified'}; reasons={','.join(reasons) or 'unclassified'}.",
        request_count=1,
        failure_code=code,
        safe_to_retry=transient,
        retry_after=retry_after if transient else None,
    )


@dataclass(slots=True)
class _RateLimiter:
    minimum_interval: float
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    _last_call: float | None = None
    _lock: Lock = field(default_factory=Lock)

    def wait(
        self,
        *,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        with self._lock:
            now = self.clock()
            if self._last_call is not None:
                remaining = self.minimum_interval - (now - self._last_call)
                if remaining > 0:
                    while remaining > 0:
                        _http_timeout(remaining, deadline, cancelled)
                        self.sleeper(min(0.1, remaining))
                        now = self.clock()
                        remaining = self.minimum_interval - (now - self._last_call)
            self._last_call = now


class AMapReverseGeocoder:
    provider_id = "amap"
    datum = MapDatum.GCJ02
    max_provider_requests_per_lookup = 1
    data_handling = "unknown"
    capabilities = GeoProviderCapabilities(
        provider_id,
        (
            GeoOperation.RESOLVE_PLACE,
            GeoOperation.REVERSE_GEOCODE,
            GeoOperation.NEARBY_PLACES,
        ),
        datum,
        operation_request_ceilings=((GeoOperation.RESOLVE_PLACE, 1),),
        repeatable_queries=True,
    )

    def __init__(
        self,
        api_key: str,
        *,
        transport: JsonTransport | None = None,
        converter: CoordinateConverter | None = None,
        endpoint: str = "https://restapi.amap.com/v3/geocode/regeo",
        timeout: float = 15,
        minimum_interval: float = 0.3,
        radius_meters: int = 200,
    ) -> None:
        if not api_key:
            raise ValueError("AMap api_key must be non-empty")
        if timeout <= 0 or minimum_interval < 0 or radius_meters < 1:
            raise ValueError("AMap timing and radius values must be positive")
        self._api_key = api_key
        self._transport = transport or UrllibJsonTransport()
        self._converter = converter or XYConvertCoordinateConverter()
        self.endpoint = endpoint
        self.timeout = timeout
        self.radius_meters = radius_meters
        self._limiter = _RateLimiter(minimum_interval)

    def lookup(self, coordinate: GeoCoordinate, *, language: str) -> GeoProviderResult:
        return self._lookup(
            coordinate,
            language=language,
            include_nearby=True,
            radius_meters=self.radius_meters,
        )

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> GeoProviderExecution:
        operation = GeoOperation(operation)
        if operation not in self.capabilities.operations:
            raise ValueError(f"AMap does not support {operation.value}")
        converted = self._converter.convert(coordinate, self.datum)
        try:
            result = self._lookup(
                coordinate,
                language=locale,
                include_nearby=operation
                in {GeoOperation.RESOLVE_PLACE, GeoOperation.NEARBY_PLACES},
                radius_meters=(
                    min(radius_meters, self.radius_meters)
                    if operation is GeoOperation.RESOLVE_PLACE
                    and radius_meters is not None
                    else radius_meters or self.radius_meters
                ),
                deadline=deadline,
                cancelled=cancelled,
            )
        except GeoLookupError as error:
            failed = _provider_error_execution(
                self.provider_id,
                (
                    GeoOperation.REVERSE_GEOCODE
                    if operation is GeoOperation.RESOLVE_PLACE
                    else operation
                ),
                coordinate,
                converted,
                error,
            )
            if operation is not GeoOperation.RESOLVE_PLACE:
                return failed
            return GeoProviderExecution(
                failed.component,
                replace(failed.attempt, operation=GeoOperation.RESOLVE_PLACE),
                (
                    GeoComponentResult(
                        GeoOperation.NEARBY_PLACES,
                        failed.component.status,
                        (),
                        coordinate,
                        qualifications=failed.component.qualifications,
                    ),
                ),
            )
        if operation is GeoOperation.RESOLVE_PLACE:
            address = _provider_execution(
                result,
                GeoOperation.REVERSE_GEOCODE,
                max_places=None,
            )
            nearby = _provider_execution(
                result,
                GeoOperation.NEARBY_PLACES,
                max_places=max_places,
            )
            return GeoProviderExecution(
                address.component,
                replace(address.attempt, operation=GeoOperation.RESOLVE_PLACE),
                (nearby.component,),
            )
        return _provider_execution(
            result,
            operation,
            max_places=max_places,
        )

    def _lookup(
        self,
        coordinate: GeoCoordinate,
        *,
        language: str,
        include_nearby: bool,
        radius_meters: float,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> GeoProviderResult:
        del language
        converted = self._converter.convert(coordinate, self.datum)
        self._limiter.wait(deadline=deadline, cancelled=cancelled)
        response = self._transport.get_json(
            self.endpoint,
            params={
                "key": self._api_key,
                "output": "json",
                "extensions": "all" if include_nearby else "base",
                "radius": radius_meters,
                "location": f"{converted.longitude:.6f},{converted.latitude:.6f}",
            },
            headers={"Accept-Language": "zh"},
            timeout=_http_timeout(self.timeout, deadline, cancelled),
        )
        if response.get("status") != "1":
            code = str(response.get("infocode") or "amap_error")
            message = str(response.get("info") or "AMap request failed")
            if code in {"10019", "10020", "10021"}:
                raise GeoTransientError(
                    "AMap temporary service rejection",
                    request_count=1,
                    safe_to_retry=True,
                    failure_code="service_transient",
                )
            if code in {
                "10001",
                "10002",
                "10005",
                "10006",
                "10007",
                "10008",
                "10009",
                "10012",
                "10013",
            }:
                raise GeoPermanentError(
                    "AMap credential or access configuration rejected",
                    request_count=1,
                    failure_code="authentication",
                )
            if code in {"10003", "10004", "10010", "10014", "10044"}:
                raise GeoPermanentError(
                    "AMap quota requires user action",
                    request_count=1,
                    failure_code="provider_quota",
                )
            return GeoProviderResult(
                "failed",
                self.provider_id,
                "zh",
                coordinate,
                converted,
                None,
                (),
                1,
                code,
                message,
            )
        regeocode = response.get("regeocode")
        if not isinstance(regeocode, Mapping):
            regeocode = {}
        formatted_address = _text(regeocode.get("formatted_address"))
        components = _string_mapping(regeocode.get("addressComponent"))
        pois_value = regeocode.get("pois") if include_nearby else ()
        pois = tuple(
            _amap_poi(item)
            for item in (pois_value if isinstance(pois_value, Sequence) else ())
            if isinstance(item, Mapping)
        )
        location = (
            None
            if not formatted_address
            else {"formatted_address": formatted_address, "components": components}
        )
        return GeoProviderResult(
            "success" if location is not None else "no_result",
            self.provider_id,
            "zh",
            coordinate,
            converted,
            location,
            pois,
            1,
        )


class GoogleMapsReverseGeocoder:
    provider_id = "google_maps"
    datum = MapDatum.WGS84
    max_provider_requests_per_lookup = 2
    data_handling = "unknown"
    capabilities = GeoProviderCapabilities(
        provider_id,
        (
            GeoOperation.RESOLVE_PLACE,
            GeoOperation.REVERSE_GEOCODE,
            GeoOperation.NEARBY_PLACES,
        ),
        datum,
        operation_request_ceilings=((GeoOperation.RESOLVE_PLACE, 2),),
        independent_components=True,
        repeatable_queries=True,
    )

    def __init__(
        self,
        api_key: str,
        *,
        transport: JsonTransport | None = None,
        converter: CoordinateConverter | None = None,
        reverse_endpoint: str = "https://maps.googleapis.com/maps/api/geocode/json",
        nearby_endpoint: str = "https://places.googleapis.com/v1/places:searchNearby",
        timeout: float = 3,
        minimum_interval: float = 0.3,
        nearby_radius_meters: float = 500,
        max_pois: int = 10,
        include_nearby: bool = True,
    ) -> None:
        if not api_key:
            raise ValueError("Google Maps api_key must be non-empty")
        if timeout <= 0 or minimum_interval < 0 or nearby_radius_meters <= 0:
            raise ValueError("Google Maps timing and radius values must be positive")
        if not 1 <= max_pois <= 20:
            raise ValueError("Google Maps max_pois must be from 1 through 20")
        self._api_key = api_key
        self._transport = transport or UrllibJsonTransport()
        self._converter = converter or XYConvertCoordinateConverter()
        self.reverse_endpoint = reverse_endpoint
        self.nearby_endpoint = nearby_endpoint
        self.timeout = timeout
        self.nearby_radius_meters = nearby_radius_meters
        self.max_pois = max_pois
        self.include_nearby = include_nearby
        self._limiter = _RateLimiter(minimum_interval)

    def lookup(self, coordinate: GeoCoordinate, *, language: str) -> GeoProviderResult:
        converted, normalized_language, reverse = self._reverse(
            coordinate, language=language
        )
        request_count = 1
        nearby: Mapping[str, object] = {}
        nearby_error: str | None = None
        if self.include_nearby:
            request_count += 1
            try:
                nearby = self._nearby(
                    converted,
                    language=normalized_language,
                    radius_meters=self.nearby_radius_meters,
                    max_places=self.max_pois,
                )
            except GeoLookupError as error:
                nearby_error = str(error) or type(error).__name__

        location = _google_location(reverse)
        places = nearby.get("places")
        pois = tuple(
            _google_poi(item, converted)
            for item in (places if isinstance(places, Sequence) else ())
            if isinstance(item, Mapping)
        )
        reverse_error = None
        if reverse.get("status") not in {"OK", "ZERO_RESULTS"}:
            reverse_error = _text(reverse.get("error_message")) or str(
                reverse.get("status") or "google_maps_error"
            )
        if location is not None and nearby_error is None:
            status = "success"
        elif location is not None or pois:
            status = "partial"
        elif reverse.get("status") == "ZERO_RESULTS" and nearby_error is None:
            status = "no_result"
        else:
            status = "failed"
        error_message = (
            "; ".join(value for value in (reverse_error, nearby_error) if value) or None
        )
        return GeoProviderResult(
            status,
            self.provider_id,
            normalized_language,
            coordinate,
            converted,
            location,
            pois,
            request_count,
            None if error_message is None else "google_maps_error",
            error_message,
        )

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> GeoProviderExecution:
        operation = GeoOperation(operation)
        if operation not in self.capabilities.operations:
            raise ValueError(f"Google Maps does not support {operation.value}")
        if operation is GeoOperation.RESOLVE_PLACE:
            reverse = self.execute(
                GeoOperation.REVERSE_GEOCODE,
                coordinate,
                locale=locale,
                deadline=deadline,
                cancelled=cancelled,
            )
            if reverse.component.status is GeoComponentStatus.INDETERMINATE:
                return GeoProviderExecution(
                    reverse.component,
                    reverse.attempt,
                    (
                        GeoComponentResult(
                            GeoOperation.NEARBY_PLACES,
                            GeoComponentStatus.NOT_REQUESTED,
                            (),
                            coordinate,
                            qualifications=(
                                {
                                    "code": "stopped_after_indeterminate_effect",
                                    "message": (
                                        "Nearby-place lookup was not admitted after "
                                        "an indeterminate reverse-geocode effect."
                                    ),
                                },
                            ),
                        ),
                    ),
                )
            nearby = self.execute(
                GeoOperation.NEARBY_PLACES,
                coordinate,
                locale=locale,
                radius_meters=radius_meters,
                max_places=max_places,
                deadline=deadline,
                cancelled=cancelled,
            )
            return GeoProviderExecution(
                reverse.component,
                reverse.attempt,
                (nearby.component,),
                (nearby.attempt,),
            )
        converted = self._converter.convert(coordinate, self.datum)
        normalized_language = _google_language(locale)
        try:
            if operation is GeoOperation.REVERSE_GEOCODE:
                converted, normalized_language, response = self._reverse(
                    coordinate, language=locale, deadline=deadline, cancelled=cancelled
                )
                status = response.get("status")
                if status == "UNKNOWN_ERROR":
                    raise GeoTransientError(
                        "Google temporary service error",
                        request_count=1,
                        safe_to_retry=True,
                        failure_code="service_transient",
                    )
                if status in {"OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT"}:
                    raise GeoPermanentError(
                        "Google quota requires user action",
                        request_count=1,
                        failure_code="provider_quota",
                    )
                if status == "REQUEST_DENIED":
                    raise GeoPermanentError(
                        "Google access configuration rejected",
                        request_count=1,
                        failure_code="authentication",
                    )
                if status == "INVALID_REQUEST":
                    raise _google_response_error("INVALID_ARGUMENT", ())
                if status not in {"OK", "ZERO_RESULTS"}:
                    raise GeoPermanentError(
                        "Google returned an unrecognized response status",
                        request_count=1,
                        failure_code="provider_response_invalid",
                    )
                location = _google_location(response)
                reverse_error = None
                if response.get("status") not in {"OK", "ZERO_RESULTS"}:
                    reverse_error = _text(response.get("error_message")) or str(
                        response.get("status") or "google_maps_error"
                    )
                result = GeoProviderResult(
                    "failed"
                    if reverse_error is not None
                    else "success"
                    if location is not None
                    else "no_result",
                    self.provider_id,
                    normalized_language,
                    coordinate,
                    converted,
                    location,
                    (),
                    1,
                    None if reverse_error is None else "google_maps_error",
                    reverse_error,
                )
            else:
                requested_radius, requested_places = radius_meters, max_places
                radius_meters = min(
                    self.nearby_radius_meters
                    if radius_meters is None
                    else radius_meters,
                    self.nearby_radius_meters,
                    50000,
                )
                max_places = min(
                    self.max_pois if max_places is None else max_places, self.max_pois
                )
                response = self._nearby(
                    converted,
                    language=normalized_language,
                    radius_meters=radius_meters,
                    max_places=max_places,
                    deadline=deadline,
                    cancelled=cancelled,
                )
                places = response.get("places")
                pois = tuple(
                    _google_poi(item, converted)
                    for item in (places if isinstance(places, Sequence) else ())
                    if isinstance(item, Mapping)
                )
                nearby_error = response.get("error")
                nearby_error = (
                    nearby_error if isinstance(nearby_error, Mapping) else None
                )
                if nearby_error is not None:
                    raise _google_response_error(*_google_error_signals(response))
                error_message = (
                    _text(nearby_error.get("message"))
                    if nearby_error is not None
                    else None
                )
                result = GeoProviderResult(
                    "failed"
                    if nearby_error is not None
                    else "success"
                    if pois
                    else "no_result",
                    self.provider_id,
                    normalized_language,
                    coordinate,
                    converted,
                    None,
                    pois,
                    1,
                    None if nearby_error is None else "google_maps_error",
                    error_message,
                )
        except GeoLookupError as error:
            if isinstance(error, (_HttpResponseError, _HttpTransientResponseError)):
                error = _google_response_error(
                    *_google_error_signals(error.response),
                    fallback=error.failure_code or "provider_http_rejected",
                    http_status=error.http_status,
                    retry_after=error.retry_after,
                )
            execution = _provider_error_execution(
                self.provider_id,
                operation,
                coordinate,
                converted,
                error,
            )
        else:
            execution = _provider_execution(result, operation, max_places=max_places)
        if operation is GeoOperation.NEARBY_PLACES and (
            requested_radius is not None
            and radius_meters < requested_radius
            or requested_places is not None
            and max_places < requested_places
        ):
            execution = replace(
                execution,
                component=replace(
                    execution.component,
                    qualifications=(
                        *execution.component.qualifications,
                        {
                            "code": "provider_bounds_narrowed",
                            "message": f"Google profile requested radius {radius_meters:g} meters and at most {max_places} places; these bounds do not establish exhaustive coverage.",
                        },
                    ),
                ),
            )
        return execution

    def _reverse(
        self,
        coordinate: GeoCoordinate,
        *,
        language: str,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[GeoCoordinate, str, Mapping[str, object]]:
        converted = self._converter.convert(coordinate, self.datum)
        normalized_language = _google_language(language)
        self._limiter.wait(deadline=deadline, cancelled=cancelled)
        reverse = self._transport.get_json(
            self.reverse_endpoint,
            params={
                "key": self._api_key,
                "latlng": f"{converted.latitude},{converted.longitude}",
                "language": normalized_language,
            },
            headers=None,
            timeout=_http_timeout(self.timeout, deadline, cancelled),
        )
        return converted, normalized_language, reverse

    def _nearby(
        self,
        converted: GeoCoordinate,
        *,
        language: str,
        radius_meters: float,
        max_places: int,
        deadline: float | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> Mapping[str, object]:
        # Final request boundary also covers lookup() and direct component callers.
        radius_meters = min(radius_meters, self.nearby_radius_meters, 50000)
        max_places = min(max_places, self.max_pois)
        if not 0 < radius_meters <= 50000 or not 1 <= max_places <= 20:
            raise ValueError("invalid Google nearby request bounds")
        self._limiter.wait(deadline=deadline, cancelled=cancelled)
        return self._transport.post_json(
            self.nearby_endpoint,
            payload={
                "includedTypes": [],
                "maxResultCount": max_places,
                "rankPreference": "DISTANCE",
                "languageCode": language,
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": converted.latitude,
                            "longitude": converted.longitude,
                        },
                        "radius": radius_meters,
                    }
                },
            },
            headers={
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": (
                    "places.displayName,places.formattedAddress,"
                    "places.primaryTypeDisplayName,places.location,places.types"
                ),
            },
            timeout=_http_timeout(self.timeout, deadline, cancelled),
        )


class AdaptiveReverseGeocoder:
    """Explicit per-batch provider continuity with bounded fallback."""

    def __init__(
        self,
        providers: Mapping[str, ReverseGeocodeProvider],
        *,
        provider_order: tuple[str, ...] = ("amap", "google_maps"),
        initial_provider: str = "google_maps",
        initial_language: str = "zh",
        max_route_attempts: int = 3,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one reverse-geocode provider is required")
        if initial_provider not in providers:
            raise ValueError("initial provider is not configured")
        if set(provider_order) != set(providers):
            raise ValueError("provider order must name each configured provider once")
        if max_route_attempts < 1:
            raise ValueError("max_route_attempts must be positive")
        self.providers = dict(providers)
        self.provider_order = provider_order
        self.initial_provider = initial_provider
        self.initial_language = initial_language
        self.current_provider = initial_provider
        self.current_language = initial_language
        self.max_route_attempts = max_route_attempts
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def reset(self) -> None:
        """Start one frozen batch from its declared route seed."""

        self.current_provider = self.initial_provider
        self.current_language = self.initial_language

    def routing_state(self) -> dict[str, str]:
        """Return the state that semantically influences the next lookup."""

        return {
            "provider": self.current_provider,
            "language": self.current_language,
        }

    def effect_disclosure(
        self, logical_query_count: int
    ) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "provider": provider_id,
                "data_handling": str(getattr(provider, "data_handling", "unknown")),
                "max_provider_requests": (
                    logical_query_count
                    * self.max_route_attempts
                    * int(getattr(provider, "max_provider_requests_per_lookup", 1))
                ),
            }
            for provider_id, provider in self.providers.items()
        )

    def lookup(self, coordinate: GeoCoordinate) -> GeoLookupResult:
        attempted: set[tuple[str, str]] = set()
        attempts: list[dict[str, object]] = []
        best: GeoProviderResult | None = None
        last: GeoProviderResult | None = None
        qualifications: list[dict[str, str]] = []
        for _attempt_number in range(self.max_route_attempts):
            combination = (self.current_provider, self.current_language)
            if combination in attempted:
                qualifications.append(
                    {
                        "code": "provider_route_exhausted",
                        "effect": "limits_interpretation",
                        "message": "No untried provider-language route remained.",
                    }
                )
                break
            attempted.add(combination)
            provider = self.providers[self.current_provider]
            try:
                result = provider.lookup(coordinate, language=self.current_language)
            except GeoTransientError as error:
                attempts.append(
                    {
                        "provider": self.current_provider,
                        "language": self.current_language,
                        "status": "failed",
                        "provider_requests": error.request_count,
                        "error": {"code": "transient", "message": str(error)},
                    }
                )
                alternate = self._alternate_provider(self.current_provider)
                if alternate is None:
                    return self._failed(
                        coordinate,
                        attempts,
                        "providers_unavailable",
                        str(error) or "All providers were unavailable",
                    )
                self.current_provider = alternate
                continue
            except GeoPermanentError as error:
                attempts.append(
                    {
                        "provider": self.current_provider,
                        "language": self.current_language,
                        "status": "failed",
                        "provider_requests": error.request_count,
                        "error": {"code": "permanent", "message": str(error)},
                    }
                )
                return self._failed(
                    coordinate,
                    attempts,
                    "provider_configuration_failed",
                    str(error) or "Provider configuration failed",
                )
            last = result
            attempts.append(
                {
                    "provider": result.provider,
                    "language": result.language,
                    "status": result.status,
                    "provider_requests": result.request_count,
                }
            )
            if result.location is not None and result.status in {"success", "partial"}:
                best = result
            next_provider, next_language = self._next_route(result)
            if (next_provider, next_language) == combination:
                return self._finalize(result, attempts, qualifications)
            if (next_provider, next_language) in attempted:
                qualifications.append(
                    {
                        "code": "provider_route_exhausted",
                        "effect": "limits_interpretation",
                        "message": "Provider fallback returned to an attempted route.",
                    }
                )
                break
            self.current_provider = next_provider
            self.current_language = next_language
        selected = best or last
        if selected is None:
            return self._failed(
                coordinate,
                attempts,
                "providers_unavailable",
                "No provider returned a result",
            )
        return self._finalize(selected, attempts, qualifications)

    def observe(self, result: Mapping[str, object]) -> None:
        """Restore deterministic routing continuity from a reused Work result."""

        route = result.get("routing_after")
        route = route if isinstance(route, Mapping) else result
        provider = route.get("provider")
        language = route.get("language")
        if provider in self.providers and isinstance(language, str) and language:
            self.current_provider = str(provider)
            self.current_language = "zh" if language == "zh-CN" else language

    def _next_route(self, result: GeoProviderResult) -> tuple[str, str]:
        if result.location is None:
            if result.provider == "amap" and "google_maps" in self.providers:
                return "google_maps", self.current_language
            return result.provider, self.current_language
        components = result.location.get("components")
        components = components if isinstance(components, Mapping) else {}
        country_code = _text(components.get("country_code")).upper()
        country = _text(components.get("country")).casefold()
        in_china = country_code == "CN" or "china" in country or "中国" in country
        provider = (
            "amap"
            if in_china and "amap" in self.providers
            else "google_maps"
            if not in_china and "google_maps" in self.providers
            else result.provider
        )
        language = _country_language(country_code, country)
        if provider == "amap":
            language = "zh"
        return provider, language

    def _alternate_provider(self, provider: str) -> str | None:
        return next((item for item in self.provider_order if item != provider), None)

    def _finalize(
        self,
        result: GeoProviderResult,
        attempts: list[dict[str, object]],
        qualifications: list[dict[str, str]],
    ) -> GeoLookupResult:
        self.current_provider, self.current_language = self._next_route(result)
        if result.status == "partial":
            qualifications.append(
                {
                    "code": "provider_result_partial",
                    "effect": "limits_interpretation",
                    "message": result.error_message
                    or "Provider returned partial data.",
                }
            )
        return GeoLookupResult(
            status=result.status,
            provider=result.provider,
            language=result.language,
            input_coordinate=result.input_coordinate,
            provider_coordinate=result.provider_coordinate,
            location=result.location,
            pois=result.pois,
            attempts=tuple(attempts),
            qualifications=tuple(qualifications),
            observed_at=self._clock().isoformat(timespec="microseconds"),
            error_code=result.error_code,
            error_message=result.error_message,
        )

    def _failed(
        self,
        coordinate: GeoCoordinate,
        attempts: list[dict[str, object]],
        code: str,
        message: str,
    ) -> GeoLookupResult:
        return GeoLookupResult(
            status="failed",
            provider=self.current_provider,
            language=self.current_language,
            input_coordinate=coordinate,
            provider_coordinate=coordinate,
            location=None,
            pois=(),
            attempts=tuple(attempts),
            qualifications=(),
            observed_at=self._clock().isoformat(timespec="microseconds"),
            error_code=code,
            error_message=message,
        )


def _google_language(language: str) -> str:
    if language == "zh":
        return "zh-CN"
    if language == "ja":
        return "ja"
    return "en"


def _country_language(country_code: str, country: str) -> str:
    by_code = {
        "CN": "zh",
        "JP": "ja",
        "KR": "ko",
        "US": "en",
        "GB": "en",
        "IN": "en",
        "DE": "de",
        "FR": "fr",
        "RU": "ru",
        "ES": "es",
        "IT": "it",
        "BR": "pt",
        "MX": "es",
        "ID": "id",
        "VN": "vi",
        "TH": "th",
    }
    if country_code in by_code:
        return by_code[country_code]
    names = {
        "china": "zh",
        "中国": "zh",
        "japan": "ja",
        "日本": "ja",
        "korea": "ko",
        "韩国": "ko",
        "united states": "en",
        "美国": "en",
    }
    return next((language for name, language in names.items() if name in country), "ja")


def _google_location(response: Mapping[str, object]) -> dict[str, object] | None:
    results = response.get("results")
    if (
        response.get("status") != "OK"
        or not isinstance(results, Sequence)
        or not results
    ):
        return None
    first = results[0]
    if not isinstance(first, Mapping):
        return None
    components: dict[str, str] = {}
    mappings = {
        "street_number": ("house_number", False),
        "route": ("road", False),
        "neighborhood": ("suburb", False),
        "sublocality_level_1": ("suburb", False),
        "locality": ("city", False),
        "administrative_area_level_1": ("state", False),
        "country": ("country", False),
        "postal_code": ("postcode", False),
        "premise": ("office", False),
        "point_of_interest": ("commercial", False),
        "establishment": ("commercial", False),
    }
    values = first.get("address_components")
    for component in values if isinstance(values, Sequence) else ():
        if not isinstance(component, Mapping):
            continue
        types = component.get("types")
        types = types if isinstance(types, Sequence) else ()
        for source, (target, _short) in mappings.items():
            if source in types and target not in components:
                components[target] = _text(component.get("long_name"))
        if "country" in types:
            components["country_code"] = _text(component.get("short_name")).upper()
    formatted = _text(first.get("formatted_address"))
    if not formatted:
        return None
    return {"formatted_address": formatted, "components": components}


def _amap_poi(poi: Mapping[str, object]) -> dict[str, object]:
    raw_location = _text(poi.get("location"))
    parts = raw_location.split(",")
    longitude = _number(parts[0], -1.0) if parts else -1.0
    latitude = _number(parts[1], -1.0) if len(parts) > 1 else -1.0
    poi_type = _text(poi.get("type"))
    return {
        "name": _text(poi.get("name")),
        "latitude": latitude,
        "longitude": longitude,
        "distance_meters": _number(poi.get("distance"), 0.0),
        "type": poi_type,
        "class": poi_type.split(";", 1)[0],
        "address": _text(poi.get("address")),
        "weight": _number(poi.get("poiweight"), -1.0),
    }


def _google_poi(
    poi: Mapping[str, object], reference: GeoCoordinate
) -> dict[str, object]:
    display = poi.get("displayName")
    display = display if isinstance(display, Mapping) else {}
    kind = poi.get("primaryTypeDisplayName")
    kind = kind if isinstance(kind, Mapping) else {}
    location = poi.get("location")
    location = location if isinstance(location, Mapping) else {}
    latitude = _number(location.get("latitude"), 0.0)
    longitude = _number(location.get("longitude"), 0.0)
    types = poi.get("types")
    types = types if isinstance(types, Sequence) and not isinstance(types, str) else ()
    return {
        "name": _text(display.get("text")),
        "latitude": latitude,
        "longitude": longitude,
        "distance_meters": (
            _haversine(reference.latitude, reference.longitude, latitude, longitude)
            if latitude and longitude
            else -1.0
        ),
        "type": _text(kind.get("text")),
        "class": _text(types[0]) if types else "",
        "address": _text(poi.get("formattedAddress")),
        "weight": -1.0,
    }


def _haversine(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    latitude_delta = radians(lat_b - lat_a)
    longitude_delta = radians(lon_b - lon_a)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(longitude_delta / 2) ** 2
    )
    return 6_371_000.0 * 2 * asin(sqrt(value))


def _wgs84_to_gcj02(longitude: float, latitude: float) -> tuple[float, float]:
    from math import cos, pi, sin, sqrt

    delta_longitude = _transform_longitude(longitude - 105, latitude - 35)
    delta_latitude = _transform_latitude(longitude - 105, latitude - 35)
    radians = latitude / 180 * pi
    magic = sin(radians)
    magic = 1 - 0.006693421622965943 * magic * magic
    root = sqrt(magic)
    delta_latitude = (
        delta_latitude
        * 180
        / ((6_378_245 * (1 - 0.006693421622965943)) / (magic * root) * pi)
    )
    delta_longitude = delta_longitude * 180 / (6_378_245 / root * cos(radians) * pi)
    return longitude + delta_longitude, latitude + delta_latitude


def _gcj02_to_wgs84(longitude: float, latitude: float) -> tuple[float, float]:
    converted_longitude, converted_latitude = _wgs84_to_gcj02(longitude, latitude)
    return (
        longitude * 2 - converted_longitude,
        latitude * 2 - converted_latitude,
    )


def _transform_latitude(longitude: float, latitude: float) -> float:
    from math import pi, sin, sqrt

    value = (
        -100
        + 2 * longitude
        + 3 * latitude
        + 0.2 * latitude * latitude
        + 0.1 * longitude * latitude
        + 0.2 * sqrt(abs(longitude))
    )
    value += (20 * sin(6 * longitude * pi) + 20 * sin(2 * longitude * pi)) * 2 / 3
    value += (20 * sin(latitude * pi) + 40 * sin(latitude / 3 * pi)) * 2 / 3
    return (
        value + (160 * sin(latitude / 12 * pi) + 320 * sin(latitude * pi / 30)) * 2 / 3
    )


def _transform_longitude(longitude: float, latitude: float) -> float:
    from math import pi, sin, sqrt

    value = (
        300
        + longitude
        + 2 * latitude
        + 0.1 * longitude * longitude
        + 0.1 * longitude * latitude
        + 0.1 * sqrt(abs(longitude))
    )
    value += (20 * sin(6 * longitude * pi) + 20 * sin(2 * longitude * pi)) * 2 / 3
    value += (20 * sin(longitude * pi) + 40 * sin(longitude / 3 * pi)) * 2 / 3
    return (
        value
        + (150 * sin(longitude / 12 * pi) + 300 * sin(longitude / 30 * pi)) * 2 / 3
    )


def _string_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): "" if isinstance(item, list) and not item else item
        for key, item in value.items()
    }


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _provider_execution(
    result: GeoProviderResult,
    operation: GeoOperation,
    *,
    max_places: int | None,
) -> GeoProviderExecution:
    candidates: tuple[GeoCandidate, ...]
    if operation is GeoOperation.REVERSE_GEOCODE:
        candidates = _address_candidates(result)
    elif operation is GeoOperation.NEARBY_PLACES:
        candidates = _place_candidates(result, max_places=max_places)
    else:  # pragma: no cover - guarded by provider capabilities
        raise ValueError(f"unsupported provider operation: {operation.value}")

    if result.status == "failed":
        status = GeoComponentStatus.FAILED
    elif candidates:
        status = GeoComponentStatus.SUCCESS
    else:
        status = GeoComponentStatus.NO_RESULT
    qualifications = ()
    if result.error_code is not None or result.error_message is not None:
        qualifications = (
            {
                "code": result.error_code or "provider_error",
                "message": result.error_message or "Provider request failed.",
            },
        )
    return GeoProviderExecution(
        GeoComponentResult(
            operation,
            status,
            (),
            result.input_coordinate,
            candidates,
            qualifications,
        ),
        GeoProviderAttempt(
            result.provider,
            operation,
            status,
            result.input_coordinate,
            result.provider_coordinate,
            result.request_count,
            None,
            result.error_code,
            result.error_message,
        ),
    )


def _provider_error_execution(
    provider: str,
    operation: GeoOperation,
    input_coordinate: GeoCoordinate,
    provider_coordinate: GeoCoordinate,
    error: GeoLookupError,
) -> GeoProviderExecution:
    status = (
        GeoComponentStatus.INDETERMINATE
        if isinstance(error, GeoTransientError)
        and error.request_count
        and not error.safe_to_retry
        else GeoComponentStatus.FAILED
    )
    code = error.failure_code or (
        "transient" if isinstance(error, GeoTransientError) else "permanent"
    )
    message = str(error) or type(error).__name__
    qualification = ({"code": code, "message": message},)
    return GeoProviderExecution(
        GeoComponentResult(
            operation,
            status,
            (),
            input_coordinate,
            qualifications=qualification,
        ),
        GeoProviderAttempt(
            provider,
            operation,
            status,
            input_coordinate,
            provider_coordinate,
            error.request_count,
            None,
            code,
            message,
            error.retry_after,
        ),
    )


def _address_candidates(result: GeoProviderResult) -> tuple[GeoCandidate, ...]:
    location = result.location
    if not isinstance(location, Mapping):
        return ()
    name = _text(location.get("formatted_address"))
    if not name:
        return ()
    raw_components = location.get("components")
    components = _string_mapping(raw_components)
    return (
        GeoCandidate(
            GeoCandidateKind.ADDRESS,
            name,
            formatted_address=name,
            coordinate=result.input_coordinate,
            components=tuple(
                sorted((str(key), str(value)) for key, value in components.items())
            ),
            provider_ref=result.provider,
        ),
    )


def _place_candidates(
    result: GeoProviderResult, *, max_places: int | None
) -> tuple[GeoCandidate, ...]:
    candidates: list[GeoCandidate] = []
    for item in result.pois[:max_places]:
        name = _text(item.get("name"))
        if not name:
            continue
        latitude = _number(item.get("latitude"), float("nan"))
        longitude = _number(item.get("longitude"), float("nan"))
        coordinate = None
        try:
            coordinate = GeoCoordinate(
                latitude,
                longitude,
                result.provider_coordinate.datum,
            )
        except ValueError:
            pass
        components = tuple(
            (key, value)
            for key, value in (
                ("type", _text(item.get("type"))),
                ("class", _text(item.get("class"))),
            )
            if value
        )
        distance = _number(item.get("distance_meters"), -1)
        candidates.append(
            GeoCandidate(
                GeoCandidateKind.PLACE,
                name,
                formatted_address=_text(item.get("address")) or None,
                coordinate=coordinate,
                distance_meters=distance if distance >= 0 else None,
                components=components,
                provider_ref=result.provider,
            )
        )
    return tuple(candidates)


__all__ = [
    "AMapReverseGeocoder",
    "AdaptiveReverseGeocoder",
    "CoordinateConverter",
    "GeoCoordinate",
    "GeoLookupError",
    "GeoLookupResult",
    "GeoPermanentError",
    "GeoProviderResult",
    "GeoTransientError",
    "GoogleMapsReverseGeocoder",
    "JsonTransport",
    "MapDatum",
    "ReverseGeocodeProvider",
    "UrllibJsonTransport",
    "XYConvertCoordinateConverter",
]
