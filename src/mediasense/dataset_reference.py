"""Canonical conversion between public Dataset references and internal IDs."""

from __future__ import annotations


DATASET_REF_PREFIX = "dataset:"


def dataset_id_from_ref(dataset_ref: object) -> str:
    """Return the internal ID represented by one public Dataset reference."""

    if not isinstance(dataset_ref, str) or not dataset_ref.startswith(
        DATASET_REF_PREFIX
    ):
        raise ValueError("dataset_ref must be a valid Dataset reference")
    return _validated_dataset_id(dataset_ref[len(DATASET_REF_PREFIX) :])


def dataset_ref_from_id(dataset_id: object) -> str:
    """Return the public reference for one internal Dataset ID."""

    return f"{DATASET_REF_PREFIX}{_validated_dataset_id(dataset_id)}"


def _validated_dataset_id(dataset_id: object) -> str:
    if (
        not isinstance(dataset_id, str)
        or not dataset_id
        or dataset_id.startswith(DATASET_REF_PREFIX)
        or any(character.isspace() for character in dataset_id)
    ):
        raise ValueError("dataset_id must be a non-prefixed Dataset identifier")
    return dataset_id
