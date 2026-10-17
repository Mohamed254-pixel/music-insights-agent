import contextlib
import io
import unittest

from powerbi.build_project import COLUMNS
from powerbi.validate_project import validate_project
from src.export_powerbi import EXPORT_COLUMNS


class PowerBIProjectTests(unittest.TestCase):
    def test_visual_bindings_and_page_layout_are_valid(self):
        with contextlib.redirect_stdout(io.StringIO()):
            validate_project()

    def test_web_export_and_native_model_use_matching_fields(self):
        self.assertEqual(
            dict((source, name) for name, source, _ in COLUMNS), EXPORT_COLUMNS
        )
