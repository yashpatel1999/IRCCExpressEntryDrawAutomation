from datetime import datetime


class ValidationResult:
    def __init__(self, is_valid, reason, confidence):
        self.is_valid = is_valid
        self.reason = reason
        self.confidence = confidence

    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "reason": self.reason,
            "confidence": self.confidence,
        }


def validate_draw_record(draw_record, now=None, max_age_days=60):
    missing_fields = []
    for field_name in ("draw_number", "draw_date", "invitations", "crs_cutoff"):
        if getattr(draw_record, field_name, None) is None:
            missing_fields.append(field_name)

    if missing_fields:
        return ValidationResult(False, "missing_fields:%s" % ",".join(missing_fields), 0.0)

    try:
        draw_date = datetime.strptime(draw_record.draw_date, "%Y-%m-%d").date()
    except Exception:
        return ValidationResult(False, "invalid_draw_date", 0.0)

    today = now.date() if now is not None else datetime.utcnow().date()
    age_days = (today - draw_date).days
    if age_days < 0:
        return ValidationResult(False, "future_draw_date", 0.0)
    if age_days > max_age_days:
        return ValidationResult(False, "stale_draw_date:%s" % age_days, 0.2)

    if getattr(draw_record, "draw_number", 0) <= 0:
        return ValidationResult(False, "invalid_draw_number", 0.0)

    if age_days <= 7:
        confidence = 1.0
    elif age_days <= 30:
        confidence = 0.8
    else:
        confidence = 0.6

    return ValidationResult(True, "valid", confidence)
