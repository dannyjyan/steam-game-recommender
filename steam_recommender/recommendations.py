"""Similarity scoring and explanations based on shared game attributes."""


WEIGHTS = {"tags": 60, "genres": 30, "developers": 10}


def recommend_games(source, candidates, limit=10):
    """Rank all candidates by weighted Jaccard overlap, with a score breakdown."""
    if type(limit) is not int or limit < 1:
        raise ValueError("Result limit must be a positive integer")
    source_attributes = {field: set(source[field]) for field in WEIGHTS}
    recommendations = []
    for game in candidates:
        if game["appid"] == source["appid"]:
            continue
        breakdown = {}
        for field, weight in WEIGHTS.items():
            attributes = set(game[field])
            shared = source_attributes[field] & attributes
            union = source_attributes[field] | attributes
            breakdown[field] = {
                "shared": sorted(shared),
                "union_count": len(union),
                "points": weight * len(shared) / len(union) if union else 0.0,
            }
        score = sum(part["points"] for part in breakdown.values())
        if score > 0:
            recommendations.append(dict(game, score=score, breakdown=breakdown))
    # Do not round or limit before ranking; both can hide a better match.
    recommendations.sort(key=lambda game: (
        -game["score"],
        -(game["reviews"] if game["reviews"] is not None else -1),
        game["name"].casefold(),
        game["appid"],
    ))
    return recommendations[:limit]
