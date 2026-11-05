def validate_token_budget(usage, cap):
    if type(usage) is not dict:
        raise ValueError("usage must be a dict")
    required_keys = {"input_tokens", "cached_input_tokens", "output_tokens"}
    if usage.keys() != required_keys:
        raise ValueError("usage must contain exactly the required token keys")
    for value in usage.values():
        if type(value) is not int or value < 0:
            raise ValueError("token counts must be nonnegative integers")
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")
    if type(cap) is not int or cap < 0:
        raise ValueError("cap must be a nonnegative integer")
    total_tokens = usage["input_tokens"] + usage["output_tokens"]
    return {"total_tokens": total_tokens, "within_budget": total_tokens <= cap}
