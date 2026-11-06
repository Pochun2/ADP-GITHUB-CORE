"""Validate task identities without modifying the supplied records."""

import re


def _validate_record(record):
    if type(record) is not dict:
        raise ValueError("Each task identity must be a dict")
    if (
        len(record) != 3
        or any(type(key) is not str for key in record)
        or set(record) != {"task_id", "issue_number", "baseline_sha"}
    ):
        raise ValueError("Invalid task identity schema")

    task_id = record["task_id"]
    issue_number = record["issue_number"]
    baseline_sha = record["baseline_sha"]

    if type(task_id) is not str or re.fullmatch(
        r"C1-[A-Z0-9][A-Z0-9_-]{2,50}", task_id
    ) is None:
        raise ValueError("Invalid task_id")
    if type(issue_number) is not int or issue_number <= 0:
        raise ValueError("Invalid issue_number")
    if type(baseline_sha) is not str or re.fullmatch(
        r"[0-9a-f]{40}", baseline_sha
    ) is None:
        raise ValueError("Invalid baseline_sha")

    return task_id, issue_number


def validate_task_identity(task, seen):
    """Return an UNSEEN identity, raising ValueError for invalid input."""
    task_id, issue_number = _validate_record(task)
    if type(seen) is not list or len(seen) > 128:
        raise ValueError("seen must be a list containing at most 128 identities")

    task_ids = set()
    issue_numbers = set()
    for record in seen:
        seen_task_id, seen_issue_number = _validate_record(record)
        if seen_task_id in task_ids or seen_issue_number in issue_numbers:
            raise ValueError("Duplicate identity in seen")
        task_ids.add(seen_task_id)
        issue_numbers.add(seen_issue_number)

    if task_id in task_ids or issue_number in issue_numbers:
        raise ValueError("Task identity already seen")

    return {
        "state": "UNSEEN",
        "task_id": task_id,
        "issue_number": issue_number,
    }
