"""Versioned cheap photographic metadata selection, units and provenance."""

from fractions import Fraction
import hashlib
import math

# Ordered tags are interpretation policy, included in Metadata Work identity.
FIELD_TAGS = {
    "camera_make": (
        "XMP:Make",
        "EXIF:Make",
        "QuickTime:Make",
        "XML:DeviceManufacturer",
        "XML:Manufacturer",
    ),
    "camera_model": (
        "XMP:Model",
        "EXIF:Model",
        "QuickTime:Model",
        "XML:DeviceModelName",
        "XML:ModelName",
        "EXIF:UniqueCameraModel",
        "QuickTime:Encoder",
    ),
    "camera_serial_number": (
        "XMP:SerialNumber",
        "EXIF:SerialNumber",
        "MakerNotes:SerialNumber",
        "QuickTime:SerialNumber",
        "XML:DeviceSerialNo",
        "XML:SerialNo",
    ),
    "camera_firmware": (
        "XMP:Firmware",
        "EXIF:Firmware",
        "MakerNotes:FirmwareVersion",
        "EXIF:FirmwareVersion",
        "XMP:FirmwareVersion",
        "QuickTime:FirmwareVersion",
        "XML:FirmwareVersion",
    ),
    "lens_model": (
        "XMP:Lens",
        "XMP:LensModel",
        "EXIF:LensModel",
        "MakerNotes:LensModel",
        "QuickTime:LensModel",
        "XML:LensModelName",
    ),
    "lens_serial_number": (
        "XMP:LensSerialNumber",
        "EXIF:LensSerialNumber",
        "MakerNotes:LensSerialNumber",
    ),
    "focal_length_mm": ("XMP:FocalLength", "EXIF:FocalLength", "QuickTime:FocalLength"),
    "focal_length_35mm_equivalent_mm": (
        "XMP:FocalLengthIn35mmFormat",
        "EXIF:FocalLengthIn35mmFormat",
        "QuickTime:FocalLengthIn35mmFormat",
    ),
    "aperture_f_number": ("XMP:FNumber", "EXIF:FNumber", "QuickTime:FNumber"),
    "exposure_time_seconds": (
        "XMP:ExposureTime",
        "EXIF:ExposureTime",
        "QuickTime:ExposureTime",
        "MakerNotes:ExposureTime",
    ),
    "iso": ("XMP:ISO", "EXIF:ISO", "QuickTime:ISO"),
    "orientation": ("XMP:Orientation", "EXIF:Orientation"),
    "media_type": ("File:MIMEType",),
    "source_file_format": ("File:FileType", "XMP:Format", "EXIF:Format"),
    "gps_altitude_meters": (
        "XMP:GPSAltitude",
        "Composite:GPSAltitude",
        "EXIF:GPSAltitude",
    ),
    "gps_version": ("XMP:GPSVersionID", "EXIF:GPSVersionID"),
}
DIMENSION_TAGS = (
    ("File:ImageWidth", "File:ImageHeight"),
    ("PNG:ImageWidth", "PNG:ImageHeight"),
    ("EXIF:ImageWidth", "EXIF:ImageHeight"),
    ("QuickTime:ImageWidth", "QuickTime:ImageHeight"),
)
EXTRA_TAGS = tuple(
    dict.fromkeys(
        [tag for tags in FIELD_TAGS.values() for tag in tags]
        + [tag for tags in DIMENSION_TAGS for tag in tags]
        + ["EXIF:GPSAltitudeRef", "XMP:GPSAltitudeRef"]
    )
)
POSITIVE = {
    "focal_length_mm",
    "focal_length_35mm_equivalent_mm",
    "aperture_f_number",
    "exposure_time_seconds",
    "iso",
}
SOURCE_ONLY = {"media_type"}


def _value(name, raw):
    if name in POSITIVE or name in {"orientation", "gps_altitude_meters"}:
        if isinstance(raw, bool):
            raise ValueError("boolean is not a measurement")
        value = float(Fraction(str(raw)))
        if not math.isfinite(value) or (name in POSITIVE and value <= 0):
            raise ValueError("invalid measurement")
        if name == "orientation":
            if not value.is_integer() or not 1 <= value <= 8:
                raise ValueError("invalid orientation")
            return int(value)
        return value
    value = str(raw).strip()
    if not value:
        raise ValueError("empty metadata")
    return value


def _custom_value(definition, raw):
    kind = definition["value_type"]
    if kind == "string":
        if isinstance(raw, (dict, list)):
            raise ValueError("structured value is not a string field")
        return _value(definition["name"], raw)
    if kind == "boolean":
        if type(raw) is bool:
            return raw
        if type(raw) in {int, float} and raw in (0, 1):
            return bool(raw)
        if isinstance(raw, str) and raw.strip().lower() in {"true", "false", "0", "1"}:
            return raw.strip().lower() in {"true", "1"}
        raise ValueError("invalid boolean field")
    if isinstance(raw, bool):
        raise ValueError("boolean is not a number")
    value = float(Fraction(str(raw)))
    if not math.isfinite(value) or (kind == "integer" and not value.is_integer()):
        raise ValueError("invalid numeric field")
    return int(value) if kind == "integer" else value


def photographic_observations(indexed, ordered, subject, profile, knowledge=None):
    knowledge = knowledge or {}
    observations = []
    effective_profile = {
        "name": profile.profile_id,
        "identity": "sha256:"
        + hashlib.sha256(profile.descriptor().encode()).hexdigest(),
        "selection": "first_valid_tag_then_source_precedence",
    }
    definitions = dict(FIELD_TAGS)
    definitions.update(
        {name: () for name in knowledge if name.startswith("manufacturer.")}
    )
    for name, default_tags in definitions.items():
        resolution = knowledge.get(name, {})
        effect = resolution.get("effect")
        declaration = resolution.get("declaration")
        if (
            declaration is not None
            and effect is None
            and not resolution.get("conflict")
        ):
            unknown = resolution["unknown"]
            observations.append(
                {
                    "name": name,
                    "status": "not_checked" if unknown else "not_applicable",
                    "basis": {
                        "code": "manufacturer_rule_applicability_unknown"
                        if unknown
                        else "manufacturer_rule_not_applicable"
                    },
                    "provenance": {
                        "definition": {
                            key: declaration[key]
                            for key in ("value_type", "description", "unit")
                            if key in declaration
                        }
                    },
                }
            )
            continue
        effect = effect or {}
        preferred = tuple(effect.get("tags", ()))
        conflict_tags = (
            resolution.get("candidate_tags", ()) if resolution.get("conflict") else ()
        )
        tags = tuple(dict.fromkeys((*preferred, *default_tags, *conflict_tags)))
        allowed = set(preferred) | (
            set(default_tags) if effect.get("fallback", True) else set()
        )
        if resolution.get("conflict"):
            allowed.update(conflict_tags)
        candidates = []
        paths = [subject.as_posix()] if name in SOURCE_ONLY else ordered
        for tag in tags:
            for path in paths:
                if tag.startswith("File:") and path != subject.as_posix():
                    continue  # A sidecar's container is not the media container.
                fields = indexed.get(path, {})
                raw = fields.get(tag)
                if raw is None or raw == "":
                    continue
                candidate = {"relative_path": path, "tag": tag, "raw_value": raw}
                if tag not in allowed:
                    candidate["rejection"] = "manufacturer_fallback_disabled"
                    candidates.append(candidate)
                    continue
                if (
                    name == "camera_model"
                    and tag == "QuickTime:Encoder"
                    and tag not in preferred
                ):
                    candidate["rejection"] = "encoder_is_not_camera_identity"
                    candidates.append(candidate)
                    continue
                try:
                    value = (
                        _custom_value(declaration, raw)
                        if declaration is not None
                        else _value(name, raw)
                    )
                    if name == "gps_altitude_meters" and tag != "Composite:GPSAltitude":
                        ref_tag = tag.split(":")[0] + ":GPSAltitudeRef"
                        altitude_ref = fields.get(ref_tag)
                        if altitude_ref is not None:
                            candidate["altitude_ref"] = altitude_ref
                            if str(altitude_ref) == "1":
                                value = -abs(value)
                        else:
                            candidate["altitude_reference"] = "unrecorded"
                    candidate["value"] = value
                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    candidate["rejection"] = "invalid_metadata_value"
                candidates.append(candidate)
        valid = [candidate for candidate in candidates if "value" in candidate]
        observation = {"name": name, "status": "available" if valid else "missing"}
        if valid:
            selected = valid[0]
            observation.update(
                value=selected["value"],
                provenance={
                    **selected,
                    "profile": effective_profile,
                    "candidates": candidates,
                },
            )
            if any(candidate["value"] != selected["value"] for candidate in valid[1:]):
                observation["qualifications"] = [
                    {
                        "code": "metadata_source_conflict",
                        "effect": "limits_interpretation",
                        "message": "Metadata sources disagree; the effective tag and source precedence selected this value.",
                    }
                ]
            if (
                name == "gps_altitude_meters"
                and selected.get("altitude_reference") == "unrecorded"
            ):
                observation.setdefault("qualifications", []).append(
                    {
                        "code": "altitude_reference_unrecorded",
                        "effect": "limits_interpretation",
                        "message": "The altitude reference was not recorded; its datum must not be inferred.",
                    }
                )
        elif candidates:
            observation["basis"] = {
                "code": "invalid_metadata_value",
                "candidates": candidates,
            }
        observation.setdefault(
            "provenance", {"profile": effective_profile, "attempted_tags": list(tags)}
        )
        if declaration is not None:
            observation["provenance"]["definition"] = {
                key: declaration[key]
                for key in ("value_type", "description", "unit")
                if key in declaration
            }
        observations.append(observation)
    fields = indexed.get(subject.as_posix(), {})
    dimension = {"name": "source_pixel_dimensions", "status": "missing"}
    for width_tag, height_tag in DIMENSION_TAGS:
        width, height = fields.get(width_tag), fields.get(height_tag)
        if type(width) is int and type(height) is int and width > 0 and height > 0:
            dimension.update(
                status="available",
                value={"width": width, "height": height},
                provenance={
                    "relative_path": subject.as_posix(),
                    "tags": [width_tag, height_tag],
                    "profile": effective_profile,
                },
            )
            break
    observations.append(dimension)
    return observations
