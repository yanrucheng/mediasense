"""Reverse-geocode behavior characterized from AI Album c90."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from mediasense.geo import (
    AdaptiveReverseGeocoder,
    GeoCoordinate,
    GeoProviderResult,
    MapDatum,
    XYConvertCoordinateConverter,
)


pytestmark = pytest.mark.characterization


@dataclass
class FakeProvider:
    provider_id: str
    datum: MapDatum
    calls: list[tuple[float, float, str]] = field(default_factory=list)

    def lookup(self, coordinate: GeoCoordinate, *, language: str) -> GeoProviderResult:
        self.calls.append((coordinate.longitude, coordinate.latitude, language))
        if coordinate.longitude < 120:
            country = "China"
            country_code = "CN"
        else:
            country = "Japan"
            country_code = "JP"
        if self.provider_id == "amap" and country_code != "CN":
            return GeoProviderResult(
                status="no_result",
                provider=self.provider_id,
                language="zh",
                input_coordinate=coordinate,
                provider_coordinate=coordinate,
                location=None,
                pois=(),
                request_count=1,
            )
        return GeoProviderResult(
            status="success",
            provider=self.provider_id,
            language=language,
            input_coordinate=coordinate,
            provider_coordinate=coordinate,
            location={
                "formatted_address": f"{country} address",
                "components": {"country": country, "country_code": country_code},
            },
            pois=(),
            request_count=2 if self.provider_id == "google_maps" else 1,
        )


def test_c90_provider_and_language_follow_the_previous_successful_region() -> None:
    amap = FakeProvider("amap", MapDatum.GCJ02)
    google = FakeProvider("google_maps", MapDatum.WGS84)
    geocoder = AdaptiveReverseGeocoder(
        providers={"amap": amap, "google_maps": google},
        initial_provider="google_maps",
        initial_language="zh",
    )

    china = geocoder.lookup(GeoCoordinate(30.6030, 114.2753, MapDatum.WGS84))
    japan = geocoder.lookup(GeoCoordinate(34.4892, 134.0897, MapDatum.WGS84))
    nearby_japan = geocoder.lookup(GeoCoordinate(34.4899, 134.0909, MapDatum.WGS84))

    assert (china.provider, china.language) == ("amap", "zh")
    assert (japan.provider, japan.language) == ("google_maps", "ja")
    assert (nearby_japan.provider, nearby_japan.language) == (
        "google_maps",
        "ja",
    )
    assert [attempt["provider"] for attempt in china.attempts] == [
        "google_maps",
        "amap",
    ]
    assert [attempt["provider"] for attempt in japan.attempts] == [
        "amap",
        "google_maps",
        "google_maps",
    ]
    assert [attempt["provider"] for attempt in nearby_japan.attempts] == ["google_maps"]


def test_c90_google_lookup_accounts_for_reverse_and_nearby_requests() -> None:
    google = FakeProvider("google_maps", MapDatum.WGS84)
    geocoder = AdaptiveReverseGeocoder(
        providers={"google_maps": google},
        provider_order=("google_maps",),
        initial_provider="google_maps",
        initial_language="ja",
    )

    result = geocoder.lookup(GeoCoordinate(35.6580, 139.7013, MapDatum.WGS84))

    assert result.logical_query_count == 1
    assert result.provider_request_count == 2
    assert result.attempts == (
        {
            "provider": "google_maps",
            "language": "ja",
            "status": "success",
            "provider_requests": 2,
        },
    )


@pytest.mark.parametrize(
    ("longitude", "latitude", "expected_longitude", "expected_latitude"),
    [
        (116.397, 39.916, 116.40324439868203, 39.917403696539274),
        (121.4737, 31.2304, 121.47822305927677, 31.228457737576967),
        (139.7013, 35.658, 139.70547640690086, 35.65828805679135),
    ],
)
def test_coordinate_conversion_matches_c90_xyconvert_samples(
    longitude: float,
    latitude: float,
    expected_longitude: float,
    expected_latitude: float,
) -> None:
    converted = XYConvertCoordinateConverter().convert(
        GeoCoordinate(latitude, longitude, MapDatum.WGS84),
        MapDatum.GCJ02,
    )

    assert converted.longitude == pytest.approx(expected_longitude, abs=1e-12)
    assert converted.latitude == pytest.approx(expected_latitude, abs=1e-12)
