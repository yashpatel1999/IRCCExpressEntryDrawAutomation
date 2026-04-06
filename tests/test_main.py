import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from ircc_draw_automation.main import main


DRAW_HTML = """
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
            <td>408</td>
            <td>April 2, 2026</td>
            <td>Trades Occupations, 2026-Version 3</td>
            <td>3,000</td>
            <td>477</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


POOL_HTML = """
<html>
  <body>
    <main>
      <details open>
        <summary>CRS score distribution of candidates in the pool as of March 29, 2026</summary>
        <table>
          <thead>
            <tr>
              <th>CRS score range</th>
              <th>Number of candidates</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>601-1200</td><td>351</td></tr>
            <tr><td>Total</td><td>230,186</td></tr>
          </tbody>
        </table>
      </details>
    </main>
  </body>
</html>
"""


class MainCliTests(unittest.TestCase):
    def test_check_latest_draw_accepts_local_html_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            draw_path = os.path.join(tempdir, "draw.html")
            pool_path = os.path.join(tempdir, "pool.html")
            state_path = os.path.join(tempdir, "state.json")

            with open(draw_path, "w", encoding="utf-8") as handle:
                handle.write(DRAW_HTML)
            with open(pool_path, "w", encoding="utf-8") as handle:
                handle.write(POOL_HTML)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "check_latest_draw",
                        "--draw-html-file",
                        draw_path,
                        "--pool-html-file",
                        pool_path,
                        "--state-file",
                        state_path,
                        "--dry-run",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn('"reason": "http_primary_success"', output)
            self.assertIn('"draw_key": "2026-04-02_408"', output)
