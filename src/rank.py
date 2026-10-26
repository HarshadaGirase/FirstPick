"""Pick the best-scoring issues from the pool."""


def top_candidates(pool, n):
    """Return the n highest-scoring issues; newer issues win ties."""
    issues = sorted(pool.values(), key=lambda i: (i["score"], i["created_at"]), reverse=True)
    return issues[:n]
