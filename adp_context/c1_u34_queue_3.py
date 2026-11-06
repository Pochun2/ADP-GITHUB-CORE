def validate_queue_3(calls, limits):
    """Validate bounded telemetry and return a nonduplicated cost rollup."""
    if type(calls) is not list or not 1 <= len(calls) <= 8:
        raise ValueError("calls must be a list containing 1 to 8 records")

    if type(limits) is not dict or limits.keys() != {
        "model", "max_tokens", "max_credits_micro"
    }:
        raise ValueError("limits must contain exactly the required keys")
    if type(limits["model"]) is not str or limits["model"] != "gpt-6.1-sol":
        raise ValueError("unsupported limits model")
    for field in ("max_tokens", "max_credits_micro"):
        if type(limits[field]) is not int or limits[field] <= 0:
            raise ValueError("limits must be strictly positive integers")

    numeric_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "credits_micro",
    )
    required_keys = {"model", *numeric_fields}
    totals = {field: 0 for field in numeric_fields}

    for call in calls:
        if type(call) is not dict or call.keys() != required_keys:
            raise ValueError("each call must contain exactly the required keys")
        if type(call["model"]) is not str or call["model"] != "gpt-6.1-sol":
            raise ValueError("unsupported call model")
        for field in numeric_fields:
            if type(call[field]) is not int or call[field] < 0:
                raise ValueError("call numeric fields must be nonnegative integers")
        if call["input_tokens"] == 0 or call["output_tokens"] == 0:
            raise ValueError("input_tokens and output_tokens must be positive")
        if call["credits_micro"] == 0:
            raise ValueError("credits_micro must be positive")
        if call["cached_input_tokens"] > call["input_tokens"]:
            raise ValueError("cached input cannot exceed input")
        if call["reasoning_tokens"] > call["output_tokens"]:
            raise ValueError("reasoning cannot exceed output")
        for field in numeric_fields:
            totals[field] += call[field]

    total_tokens = totals["input_tokens"] + totals["output_tokens"]
    if total_tokens > limits["max_tokens"]:
        raise ValueError("total tokens exceed the limit")
    if totals["credits_micro"] > limits["max_credits_micro"]:
        raise ValueError("total credits exceed the limit")

    return {
        "state": "ACCOUNTED",
        "calls": len(calls),
        "input_tokens": totals["input_tokens"],
        "cached_input_tokens": totals["cached_input_tokens"],
        "output_tokens": totals["output_tokens"],
        "reasoning_tokens_in_output": totals["reasoning_tokens"],
        "total_tokens_nonduplicated": total_tokens,
        "credits_micro": totals["credits_micro"],
        "actual_billed_usd": "UNKNOWN_NOT_IN_CLI_TELEMETRY",
    }
