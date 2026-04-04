from ircc_draw_automation.parser import parse_latest_draw


SAMPLE_HTML = """
<html>
  <body>
    <main>
      <table>
        <tbody>
          <tr>
            <td>Express Entry round #341</td>
            <td>March 20, 2026</td>
            <td>Canadian Experience Class</td>
            <td>Invitations issued: 7,500</td>
            <td>CRS score of lowest-ranked candidate invited: 515</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


TABLE_WITH_HEADER_HTML = """
<html>
  <body>
    <main>
      <table>
        <thead>
          <tr>
            <th>Round</th>
            <th>Date</th>
            <th>Program</th>
            <th>Invitations issued</th>
            <th>CRS score of lowest-ranked candidate invited</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>341</td>
            <td>March 20, 2026</td>
            <td>Canadian Experience Class</td>
            <td>7,500</td>
            <td>515</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


def test_parse_latest_draw_extracts_expected_fields():
    parsed = parse_latest_draw(
        html=SAMPLE_HTML,
        source_url="https://example.com/express-entry-rounds.html",
    )

    assert parsed.draw_key == "2026-03-20_341"
    assert parsed.draw_number == 341
    assert parsed.draw_date == "2026-03-20"
    assert parsed.program == "Canadian Experience Class"
    assert parsed.invitations == 7500
    assert parsed.crs_cutoff == 515


def test_parse_latest_draw_prefers_table_body_row_over_header_labels():
    parsed = parse_latest_draw(
        html=TABLE_WITH_HEADER_HTML,
        source_url="https://example.com/express-entry-rounds.html",
    )

    assert parsed.draw_key == "2026-03-20_341"
    assert parsed.draw_number == 341
    assert parsed.draw_date == "2026-03-20"
    assert parsed.program == "Canadian Experience Class"
    assert parsed.invitations == 7500
    assert parsed.crs_cutoff == 515
