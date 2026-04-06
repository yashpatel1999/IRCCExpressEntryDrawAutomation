def build_message(draw_record):
    return "New IRCC Draw #{0} ({1}) | Program: {2} | ITAs: {3} | CRS: {4}".format(
        draw_record.draw_number,
        draw_record.draw_date,
        draw_record.program or "Unknown",
        draw_record.invitations,
        draw_record.crs_cutoff,
    )


def build_pool_distribution_message(distribution_record):
    return "IRCC CRS pool distribution updated ({0}) | Total candidates: {1}".format(
        distribution_record.distribution_date or "date unavailable",
        distribution_record.total_candidates if distribution_record.total_candidates is not None else "unknown",
    )
