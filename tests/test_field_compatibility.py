import unittest

from xiaomang_pattern_lab.field_compatibility import audit_field_compatibility, compatibility_matrix
from xiaomang_pattern_lab.field_ui import field_description, field_label


class SharedFieldCompatibilityTests(unittest.TestCase):
    def test_audit_uses_formal_evaluation_path(self):
        rows = audit_field_compatibility()
        self.assertEqual(10, len(rows))
        by_id = {row.field: row for row in rows}
        for field_id in ("constant", "linear_x", "linear_y", "ring", "wave", "stripe", "checker", "spiral"):
            self.assertEqual("supported", by_id[field_id].size, field_id)
            self.assertEqual("supported", by_id[field_id].rotation, field_id)
        self.assertEqual("supported (legacy)", by_id["radial"].size)
        self.assertEqual("unsupported", by_id["radial"].rotation)

    def test_position_is_explicitly_unsupported(self):
        matrix = compatibility_matrix()
        self.assertTrue(all(row["position"] == "unsupported" for row in matrix.values()))

    def test_ui_ids_remain_stable_while_labels_are_chinese(self):
        self.assertEqual("波浪场", field_label("wave"))
        self.assertEqual("按周期波形重复改变参数。", field_description("wave"))


if __name__ == "__main__":
    unittest.main()
