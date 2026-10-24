"""The entire model-facing action surface. No SQL or identifier arguments."""

from datetime import date


class AgentError(Exception):
    """Safe, user-facing error; never include credentials or provider bodies."""


COMMON = {
    "start_date": {"type": ["string", "null"], "description": "Inclusive local date YYYY-MM-DD, or null."},
    "end_date": {"type": ["string", "null"], "description": "Exclusive local date YYYY-MM-DD, or null."},
    "device": {"type": ["string", "null"], "description": "Exact device label: e.g. IPHONE, MACINTOSH, GAME_CONSOLE, Unknown Device; null means all."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 60},
}
DESCRIPTIONS = {
    "top_tracks": "Rank normalized song + album pairs by hours or playback events. Does not group by artist.",
    "monthly_listening": "Monthly listening hours, eligible event counts, song + album counts, and skip rates. Dated events only. Latest months first.",
    "device_usage": "Device listening hours, eligible event counts and skip rates, ranked by hours.",
    "skip_rates": "Skipped event count, eligible event count and count-weighted skip percentage; overall or by device/month.",
    "clarify": "Decline unsupported requests (SQL, writes, causes, artists, other datasets) or request clarification of ambiguous intent, dates, metric, or multiple questions.",
}


def schemas():
    result = {}
    for name in DESCRIPTIONS:
        props = dict(COMMON)
        if name == "top_tracks":
            props["rank_by"] = {"type": "string", "enum": ["hours", "events"]}
        elif name == "skip_rates":
            props["group_by"] = {"type": "string", "enum": ["overall", "device", "month"]}
        elif name == "clarify":
            props = {"reason": {"type": "string", "enum": ["unsupported", "ambiguous", "dates"]}}
        result[name] = {"type": "object", "properties": props,
                        "required": list(props), "additionalProperties": False}
    return result


SCHEMAS = schemas()
FUNCTIONS = [{"type": "function", "name": name, "description": DESCRIPTIONS[name],
              "strict": True, "parameters": schema} for name, schema in SCHEMAS.items()]


def validate_call(name, arguments):
    """Independent runtime validation even when a provider promises strict JSON."""
    if not isinstance(name, str) or name not in SCHEMAS or not isinstance(arguments, dict):
        raise AgentError("The model returned an unapproved tool or invalid arguments.")
    if set(arguments) != set(SCHEMAS[name]["properties"]):
        raise AgentError("The tool arguments do not match the approved contract.")
    if name == "clarify":
        if arguments["reason"] not in ("unsupported", "ambiguous", "dates"):
            raise AgentError("Invalid clarification reason.")
        return dict(arguments)
    limit = arguments["limit"]
    if type(limit) is not int or not 1 <= limit <= 60:
        raise AgentError("The result limit must be an integer from 1 to 60.")
    parsed = {}
    for key in ("start_date", "end_date"):
        value = arguments[key]
        if value is not None:
            if not isinstance(value, str):
                raise AgentError("Dates must be YYYY-MM-DD strings or null.")
            try:
                value_date = date.fromisoformat(value)
            except ValueError:
                raise AgentError("Dates must be valid YYYY-MM-DD dates.") from None
            if value_date.isoformat() != value:
                raise AgentError("Dates must be canonical YYYY-MM-DD dates.")
        parsed[key] = value
    if bool(parsed["start_date"]) != bool(parsed["end_date"]):
        raise AgentError("Provide both date boundaries, or leave both null for all time.")
    if parsed["start_date"] and parsed["start_date"] >= parsed["end_date"]:
        raise AgentError("The exclusive end date must follow the start date.")
    device = arguments["device"]
    if device is not None and (not isinstance(device, str) or not device.strip()
                               or len(device) > 100 or any(ord(c) < 32 for c in device)):
        raise AgentError("The device filter must be a nonempty label of at most 100 characters.")
    if name == "top_tracks" and arguments["rank_by"] not in ("hours", "events"):
        raise AgentError("Track ranking supports hours or events only.")
    if name == "skip_rates" and arguments["group_by"] not in ("overall", "device", "month"):
        raise AgentError("Skip rates support overall, device, or month only.")
    return dict(arguments)
