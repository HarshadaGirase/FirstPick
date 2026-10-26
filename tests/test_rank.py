from src.rank import top_candidates


def test_top_candidates_sorted_by_score_newer_wins_ties():
    pool = {
        "a": {"url": "a", "score": 1.0, "created_at": "2026-10-01T00:00:00Z"},
        "b": {"url": "b", "score": 3.0, "created_at": "2026-10-01T00:00:00Z"},
        "c": {"url": "c", "score": 1.0, "created_at": "2026-10-20T00:00:00Z"},
    }
    assert [i["url"] for i in top_candidates(pool, 2)] == ["b", "c"]
    assert [i["url"] for i in top_candidates(pool, 10)] == ["b", "c", "a"]
