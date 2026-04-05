def build_message(draw_record):
    return "New IRCC Draw #{0} ({1}) | Program: {2} | ITAs: {3} | CRS: {4}".format(
        draw_record.draw_number,
        draw_record.draw_date,
        draw_record.program or "Unknown",
        draw_record.invitations,
        draw_record.crs_cutoff,
    )
