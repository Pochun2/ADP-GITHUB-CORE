"""Validate the link between two consecutive round records."""

import re


def _validate_record(record):
    if not isinstance(record, dict):
        raise ValueError("Each record must be a dict.")
    if record.keys() != {"baseline_sha", "merge_sha", "issue_number"}:
        raise ValueError("Each record must contain exactly the required keys.")

    for key in ("baseline_sha", "merge_sha"):
        value = record[key]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ValueError("SHAs must be lowercase 40-character hexadecimal strings.")

    issue_number = record["issue_number"]
    if type(issue_number) is not int or issue_number <= 0:
        raise ValueError("Issue numbers must be positive integers, excluding bool.")
    if record["merge_sha"] == record["baseline_sha"]:
        raise ValueError("A record's merge SHA must differ from its baseline SHA.")


def validate_round_link(previous, current):
    """Return the linked-round result, or raise ValueError for invalid input."""
    _validate_record(previous)
    _validate_record(current)

    if current["baseline_sha"] != previous["merge_sha"]:
        raise ValueError("The current baseline must equal the previous merge SHA.")
    if current["issue_number"] == previous["issue_number"]:
        raise ValueError("Consecutive rounds must have different issue numbers.")
    if current["merge_sha"] in (previous["baseline_sha"], previous["merge_sha"]):
        raise ValueError("The current merge SHA must not reverse or replay the chain.")

    return {
        "state": "LINKED",
        "from_sha": previous["merge_sha"],
        "to_sha": current["merge_sha"],
        "issue_pair": [previous["issue_number"], current["issue_number"]],
    }
