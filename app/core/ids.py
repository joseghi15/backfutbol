import secrets
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def build_initials(name: str) -> str:
    parts = [part for part in name.strip().split() if part]

    if not parts:
        return "EQ"

    if len(parts) == 1:
        return parts[0][:2].upper()

    return f"{parts[0][0]}{parts[-1][0]}".upper()


def build_tag(first_name: str, last_name: str) -> str:
    initials = build_initials(f"{first_name} {last_name}")
    number = secrets.randbelow(9000) + 1000
    return f"#{initials}-{number}"


def build_team_code() -> str:
    number = secrets.randbelow(9000) + 1000
    return f"EQ-{number}"
