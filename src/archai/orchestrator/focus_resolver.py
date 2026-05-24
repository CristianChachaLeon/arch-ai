import re


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def _substring_match(query_tokens: set[str], text_tokens: set[str]) -> int:
    count = 0
    for qt in query_tokens:
        for tt in text_tokens:
            if qt in tt:
                count += 1
                break
    return count


def resolve_focus(
    query: str,
    clusters: dict[str, list[str]],
    cluster_descriptions: dict[str, str] | None = None,
) -> tuple[str, str]:
    if not query or not clusters:
        return ("unknown", "No subsystem matched the query")

    query_tokens = _tokenize(query)
    if not query_tokens:
        return ("unknown", "No subsystem matched the query")

    best_cluster: str | None = None
    best_score = 0

    for cluster_name, files in clusters.items():
        score = 0

        cluster_tokens = _tokenize(cluster_name)
        score += _substring_match(query_tokens, cluster_tokens)

        for filepath in files:
            file_tokens = _tokenize(filepath)
            score += _substring_match(query_tokens, file_tokens)

        if cluster_descriptions and cluster_name in cluster_descriptions:
            desc_tokens = _tokenize(cluster_descriptions[cluster_name])
            score += _substring_match(query_tokens, desc_tokens)

        if score > best_score:
            best_score = score
            best_cluster = cluster_name

    if best_cluster is None or best_score == 0:
        return ("unknown", "No subsystem matched the query")

    return (
        best_cluster,
        f"matched query terms against cluster '{best_cluster}' with {best_score} hit(s)",
    )
