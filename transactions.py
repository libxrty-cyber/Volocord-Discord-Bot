

TRADE = "trade"
EXTENSION = "extension"
SIGNING = "signing"
RELEASE = "release"


SEASON_START = "2026-02-09"


import re


def split_transaction_clauses(description: str) -> list[str]:

    raw = (description or "").strip()
    if raw.endswith("."):
        raw = raw[:-1]
    if not raw:
        return []
    parts = re.split(r"(?<=[A-Za-z]{3})\.\s+", raw)
    return [p.strip() + "." for p in parts if p.strip()]


def classify_clause(clause: str) -> str | None:
    lower = clause.lower()
    if "acquired" in lower or "traded" in lower:
        return TRADE
    if "re-signed" in lower:
        return EXTENSION
    if "signed" in lower:
        return SIGNING
    if "waived" in lower or "released" in lower:
        return RELEASE
    return None


def team_matches(team: dict, team_query: str) -> bool:
    query = team_query.strip().lower()
    if not query:
        return True
    candidates = (
        team.get("displayName", ""),
        team.get("name", ""),
        team.get("location", ""),
        team.get("abbreviation", ""),
    )
    return any(query == c.lower() or query in c.lower() for c in candidates if c)


_DEDUP_STOPWORDS = {
    "a", "the", "and", "for", "from", "to", "in", "exchange", "draft",
    "pick", "picks", "of", "with", "trade", "traded", "acquired",
}


def _clause_fingerprint(clause: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+", clause.lower())
    return {w for w in words if w not in _DEDUP_STOPWORDS}


def _is_near_duplicate(a: str, b: str, threshold: float = 0.5) -> bool:

    fa, fb = _clause_fingerprint(a), _clause_fingerprint(b)
    if not fa or not fb:
        return False
    return len(fa & fb) / len(fa | fb) >= threshold


def filter_transactions(all_transactions: list[dict], team_query: str, category: str, since_iso: str = SEASON_START) -> list[dict]:

    query = team_query.strip().lower()
    results = []
    for t in all_transactions:
        date_str = t.get("date", "")
        if date_str and date_str[:10] < since_iso:
            continue
        team = t.get("team", {})
        for clause in split_transaction_clauses(t.get("description", "")):
            if classify_clause(clause) != category:
                continue
            if category == TRADE:
                matches = team_matches(team, team_query) or (query and query in clause.lower())
            else:
                matches = team_matches(team, team_query)
            if matches:
                results.append({"date": date_str, "team": team, "clause": clause})

    results.sort(key=lambda r: r["date"], reverse=True)

    deduped: list[dict] = []
    for r in results:
        is_dup = any(_is_near_duplicate(r["clause"], kept["clause"]) for kept in deduped)
        if not is_dup:
            deduped.append(r)

    return deduped
