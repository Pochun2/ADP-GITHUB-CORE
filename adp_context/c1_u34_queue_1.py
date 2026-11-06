"""Strict, side-effect-free validation for C1-U34-QUEUE-1 issue intake."""

import re


def validate_queue_1(manifest, issue):
    """Validate an intake pair and return READY, or raise ValueError."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a dict")
    if set(manifest) != {
        "task_id", "repository", "baseline_sha", "source_path", "spec_sha256"
    }:
        raise ValueError("manifest has incorrect keys")
    if not all(isinstance(value, str) for value in manifest.values()):
        raise ValueError("manifest values must be strings")

    if re.fullmatch(r"C1-[A-Z0-9][A-Z0-9_-]{2,50}", manifest["task_id"]) is None:
        raise ValueError("invalid task_id")
    if manifest["repository"] != "Pochun2/ADP-GITHUB-CORE":
        raise ValueError("invalid repository")
    if re.fullmatch(r"[0-9a-f]{40}", manifest["baseline_sha"]) is None:
        raise ValueError("invalid baseline_sha")
    if re.fullmatch(r"[0-9a-f]{64}", manifest["spec_sha256"]) is None:
        raise ValueError("invalid spec_sha256")
    if re.fullmatch(r"adp_context/[a-z][a-z0-9_]{1,70}\.py", manifest["source_path"]) is None:
        raise ValueError("invalid source_path")

    if not isinstance(issue, dict):
        raise ValueError("issue must be a dict")
    if set(issue) != {"number", "title", "state", "labels", "body"}:
        raise ValueError("issue has incorrect keys")
    if type(issue["number"]) is not int or issue["number"] <= 0:
        raise ValueError("issue number must be a positive integer")
    if not isinstance(issue["title"], str):
        raise ValueError("issue title must be a string")
    if issue["title"] != "[ADP-C1] " + manifest["task_id"]:
        raise ValueError("incorrect issue title")
    if not isinstance(issue["state"], str) or issue["state"] != "open":
        raise ValueError("issue must be open")
    if not isinstance(issue["labels"], list):
        raise ValueError("issue labels must be a list")
    if not all(isinstance(label, str) for label in issue["labels"]):
        raise ValueError("issue labels must contain strings")
    if issue["labels"] != ["adp-agent-ready"]:
        raise ValueError("incorrect issue labels")

    expected_body = {
        "schema": "adp-c1-issue-v1",
        "task_id": manifest["task_id"],
        "repository": manifest["repository"],
        "baseline_sha": manifest["baseline_sha"],
        "kind": "PURE_PYTHON_ONE_FILE",
        "output_path": manifest["source_path"],
        "spec_sha256": manifest["spec_sha256"],
    }
    body = issue["body"]
    if not isinstance(body, dict):
        raise ValueError("issue body must be a dict")
    if set(body) != set(expected_body):
        raise ValueError("issue body has incorrect keys")
    if not all(isinstance(value, str) for value in body.values()):
        raise ValueError("issue body values must be strings")
    if body != expected_body:
        raise ValueError("issue body does not match the manifest")

    return {
        "state": "READY",
        "task_id": manifest["task_id"],
        "issue_number": issue["number"],
    }
