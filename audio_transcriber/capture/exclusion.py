"""Exclusion rules — skip recording meetings matching title patterns or attendee blocklist."""
import re


def title_excluded(title: str, cfg: dict) -> tuple[bool, str | None]:
    """Returns (excluded, reason). Reason is the matching pattern or None."""
    if not title:
        return False, None
    patterns = cfg.get("exclusion", {}).get("title_patterns", [])
    for pat in patterns:
        try:
            if re.search(pat, title):
                return True, pat
        except re.error:
            continue
    return False, None


def attendee_excluded(attendees: list[str], cfg: dict) -> tuple[bool, str | None]:
    """Check email-suffix blocklist against attendee emails."""
    blocklist = cfg.get("exclusion", {}).get("attendee_email_blocklist", [])
    if not attendees or not blocklist:
        return False, None
    for email in attendees:
        email_lower = (email or "").lower()
        for blocked in blocklist:
            blocked_lower = blocked.lower().lstrip("@")
            if email_lower.endswith("@" + blocked_lower) or email_lower == blocked_lower:
                return True, email
    return False, None


def should_record(title: str, attendees: list[str], cfg: dict) -> tuple[bool, str]:
    """Combined check. Returns (allowed, log_message)."""
    excluded, reason = title_excluded(title, cfg)
    if excluded:
        return False, f"skipped — title matched exclusion '{reason}'"
    excluded, reason = attendee_excluded(attendees, cfg)
    if excluded:
        return False, f"skipped — attendee on blocklist ({reason})"
    return True, "ok"
