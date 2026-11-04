import re


def validate_lineage(records, initial_sha):
    """Validate a commit lineage without modifying its input records."""
    if not isinstance(initial_sha, str) or re.fullmatch(r"[0-9a-f]{40}", initial_sha) is None:
        raise ValueError("initial_sha must be a lowercase 40-hex string")
    if not isinstance(records, list) or not 1 <= len(records) <= 16:
        raise ValueError("records must be a list containing 1 through 16 dicts")

    required_keys = {"sequence", "base_sha", "merge_sha", "candidate_sha256"}
    seen_shas = {initial_sha}
    seen_candidates = set()
    expected_base = initial_sha
    final_candidate = None

    for expected_sequence, record in enumerate(records, start=1):
        if not isinstance(record, dict) or set(record) != required_keys:
            raise ValueError("each record must be a dict with exactly the required keys")

        sequence = record["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence != expected_sequence:
            raise ValueError("sequence must be an integer starting at 1 with no gaps")

        base_sha = record["base_sha"]
        merge_sha = record["merge_sha"]
        candidate = record["candidate_sha256"]
        for sha in (base_sha, merge_sha):
            if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
                raise ValueError("SHA values must be lowercase 40-hex strings")
        if not isinstance(candidate, str) or re.fullmatch(r"[0-9a-f]{64}", candidate) is None:
            raise ValueError("candidate_sha256 must be a lowercase 64-hex string")

        if base_sha != expected_base:
            raise ValueError("base_sha does not match the preceding commit")
        if merge_sha == base_sha or merge_sha in seen_shas:
            raise ValueError("merge_sha repeats a commit or creates a cycle")
        if candidate in seen_candidates:
            raise ValueError("candidate_sha256 must not repeat")

        seen_shas.add(merge_sha)
        seen_candidates.add(candidate)
        expected_base = merge_sha
        final_candidate = candidate

    return {
        "state": "VALID",
        "steps": len(records),
        "final_sha": expected_base,
        "final_candidate_sha256": final_candidate,
    }
