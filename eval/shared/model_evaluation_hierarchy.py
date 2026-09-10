"""Candidate evaluation port of AI Album's visual LinearHierarchicalCluster.

Reference: c90aa8f04fd0d3348284e0ad19e18462987b1af2, src/cluster/linear.py,
SHA-256 c13be4830ace2aa2e7507102a2451884775568b8c63dd40b454e8aa253144bce.
No runtime import from AI Album. Activation requires confirmed session config.
This is ordered adjacent splitting, NOT agglomerative clustering/linkage.
"""

import math


def linear_hierarchical(records: list[dict], vectors: dict, parameters: dict) -> dict:
    levels = parameters["distance_levels"]
    minimum = parameters["min_cluster_weight"]
    if not levels or any(
        not math.isfinite(level) or not 0 <= level <= 2 for level in levels
    ):
        raise ValueError("Cosine distance levels must be in [0, 2]")
    if levels != sorted(levels, reverse=True) or minimum < 0:
        raise ValueError(
            "Levels must be coarse to fine, with nonnegative minimum weight"
        )
    ordered = sorted(
        records, key=lambda row: (row["timestamp"], row["source"], row["id"])
    )
    identities = [row["id"] for row in ordered]
    if set(identities) != set(vectors) or len(set(identities)) != len(identities):
        raise ValueError("Every classification input needs exactly one matching vector")

    def distance(left, right):
        a, b = vectors[left], vectors[right]
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        return 1 - dot / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))

    def split(members, depth):
        if depth >= len(levels) or len(members) <= minimum or len(members) <= 1:
            return {"members": members}
        partitions = [[members[0]]]
        for previous, current in zip(members, members[1:]):
            if distance(previous, current) >= levels[depth]:
                partitions.append([])
            partitions[-1].append(current)
        # Preserve the historical early-stop behavior: one partition stops here,
        # even if a later, tighter distance level could have split it.
        if len(partitions) == 1:
            return {"members": members}
        merged = [partitions[0]]
        for partition in partitions[1:]:
            # Strict '<', not '<=': this is not a minimum final group size.
            if len(merged[-1]) + len(partition) < minimum:
                merged[-1].extend(partition)
            else:
                merged.append(partition)
        return {
            "distance_level": levels[depth],
            "children": [split(group, depth + 1) for group in merged],
        }

    return split(identities, 0)


def leaf_members(tree: dict) -> list[str]:
    if "members" in tree:
        return list(tree["members"])
    return [member for child in tree["children"] for member in leaf_members(child)]
