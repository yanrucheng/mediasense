"""Stable facade for adaptive compression strategy and Work production."""

from ._compression_producer import (
    AdaptiveCompressionProducer,
    CompressionGroupOutcome,
    CompressionInput,
)
from ._compression_strategy import (
    AdaptiveCompressionProfile,
    CompressionGroup,
    CompressionPoint,
    build_adaptive_groups,
    select_embedding_representative,
)

__all__ = [
    "AdaptiveCompressionProducer",
    "AdaptiveCompressionProfile",
    "CompressionGroup",
    "CompressionGroupOutcome",
    "CompressionInput",
    "CompressionPoint",
    "build_adaptive_groups",
    "select_embedding_representative",
]
