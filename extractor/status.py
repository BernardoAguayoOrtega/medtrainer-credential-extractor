"""expiration_status is computed in code, never by the model.

Boundaries (not specified by the brief, chosen and documented here):
- A credential is still usable on its expiration day, so it is "expired" only
  when the expiration date is before the reference date.
- "expiring_soon" covers 0 to window_days days left, both inclusive.
"""

from datetime import date

DEFAULT_WINDOW_DAYS = 60


def expiration_status(
    is_credential: bool,
    expiration_date: str | None,
    reference: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> str | None:
    if not is_credential:
        return None
    if expiration_date is None:
        return "no_expiration"
    days_left = (date.fromisoformat(expiration_date) - reference).days
    if days_left < 0:
        return "expired"
    if days_left <= window_days:
        return "expiring_soon"
    return "valid"
