def build_message(draw_record):
    return "New IRCC Draw #{0} ({1}) | Program: {2} | ITAs: {3} | CRS: {4}".format(
        draw_record.draw_number,
        draw_record.draw_date,
        draw_record.program or "Unknown",
        draw_record.invitations,
        draw_record.crs_cutoff,
    )


def build_pool_distribution_message(distribution_record):
    highlights = _format_pool_distribution_highlights(distribution_record.rows)
    base_message = "IRCC CRS pool distribution updated ({0}) | Total candidates: {1}".format(
        distribution_record.distribution_date or "date unavailable",
        distribution_record.total_candidates if distribution_record.total_candidates is not None else "unknown",
    )
    if highlights:
        return "{0} | {1}".format(base_message, highlights)
    return base_message


def _format_pool_distribution_highlights(rows):
    if not rows:
        return ""

    highlighted_rows = []
    for row in rows:
        range_label = row.get("range_label")
        candidate_count = row.get("candidate_count")
        if not range_label or candidate_count is None:
            continue
        if str(range_label).strip().lower() == "total":
            continue
        highlighted_rows.append("{0}: {1}".format(range_label, candidate_count))
        if len(highlighted_rows) == 3:
            break

    return " | ".join(highlighted_rows)
