from pathlib import Path
import importlib.util
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/generate_divination_disc_vectors.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("disc_vectors", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载矢量生成器：{SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elements(path: Path, role: str):
    root = ET.parse(path).getroot()
    return [node for node in root.iter() if node.attrib.get("data-role") == role]


def child_elements(node, role: str):
    return [child for child in node.iter() if child.attrib.get("data-role") == role]


def segment_distance_from_center(x1, y1, x2, y2, center=512):
    dx, dy = x2 - x1, y2 - y1
    length_squared = dx * dx + dy * dy
    t = ((center - x1) * dx + (center - y1) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    nearest_x, nearest_y = x1 + t * dx, y1 + t * dy
    return ((nearest_x - center) ** 2 + (nearest_y - center) ** 2) ** 0.5


class DivinationDiscVectorTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "矢量生成器尚未实现")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output = Path(self.temp_dir.name)
        load_generator().build_assets(self.output)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_blank_master_is_circular_and_has_exactly_six_empty_slots(self):
        master = self.output / "disc-master.svg"
        rings = elements(master, "disc-ring")
        slots = elements(master, "empty-slot")

        self.assertGreaterEqual(len(rings), 5)
        self.assertTrue(all(ring.attrib["cx"] == ring.attrib["cy"] for ring in rings))
        self.assertEqual(len(slots), 6)
        self.assertFalse(elements(master, "filled-yao"))

    def test_partial_state_is_bottom_up_yang_yin_yin(self):
        lines = elements(self.output / "state-partial-3.svg", "filled-yao")

        self.assertEqual(
            [line.attrib["data-kind"] for line in lines],
            ["yang", "yin", "yin"],
        )
        self.assertEqual(
            [line.attrib["data-position"] for line in lines],
            ["1", "2", "3"],
        )

    def test_shanlei_yi_has_exact_six_line_topology(self):
        lines = elements(self.output / "state-shanlei-yi.svg", "filled-yao")

        self.assertEqual(
            [line.attrib["data-kind"] for line in lines],
            ["yang", "yin", "yin", "yin", "yin", "yang"],
        )
        self.assertEqual(
            [line.attrib["data-position"] for line in lines],
            ["1", "2", "3", "4", "5", "6"],
        )

    def test_constellation_links_stay_outside_inner_clear_zone(self):
        links = elements(self.output / "disc-master.svg", "constellation-link")
        self.assertGreaterEqual(len(links), 8)

        for link in links:
            values = [
                float(value)
                for value in re.findall(r"-?\d+(?:\.\d+)?", link.attrib["d"])
            ]
            points = list(zip(values[0::2], values[1::2]))
            for start, end in zip(points, points[1:]):
                self.assertGreaterEqual(
                    segment_distance_from_center(*start, *end),
                    224,
                )

    def test_yang_and_yin_components_share_width_and_have_exact_gap(self):
        yang = elements(self.output / "component-yang.svg", "filled-yao")[0]
        yin = elements(self.output / "component-yin.svg", "filled-yao")[0]
        yin_segments = [child for child in yin if child.tag.endswith("line")]

        self.assertEqual(float(yang.attrib["x2"]) - float(yang.attrib["x1"]), 244)
        self.assertEqual(len(yin_segments), 2)
        self.assertEqual(float(yin_segments[0].attrib["x1"]), 390)
        self.assertEqual(float(yin_segments[1].attrib["x2"]), 634)
        self.assertEqual(
            float(yin_segments[1].attrib["x1"])
            - float(yin_segments[0].attrib["x2"]),
            34,
        )

    def test_design_board_reuses_one_disc_symbol(self):
        board = self.output / "design-board.svg"
        instances = elements(board, "disc-instance")

        self.assertEqual(len(instances), 6)
        self.assertEqual({node.attrib["href"] for node in instances}, {"#disc-master"})

    def test_design_board_symbol_is_definition_only_for_coresvg(self):
        root = ET.parse(self.output / "design-board.svg").getroot()
        direct_symbols = [child for child in root if child.tag.endswith("symbol")]
        defined_symbols = [
            node
            for child in root
            if child.tag.endswith("defs")
            for node in child
            if node.tag.endswith("symbol") and node.attrib.get("id") == "disc-master"
        ]

        self.assertFalse(direct_symbols)
        self.assertEqual(len(defined_symbols), 1)

    def test_design_board_workflow_states_have_exact_yao_topology(self):
        states = elements(self.output / "design-board.svg", "workflow-state")
        by_stage = {state.attrib["data-stage"]: state for state in states}
        self.assertEqual(set(by_stage), {"4", "5", "6"})
        stage_four = child_elements(by_stage["4"], "filled-yao")
        stage_five = child_elements(by_stage["5"], "filled-yao")
        stage_six = child_elements(by_stage["6"], "filled-yao")

        self.assertEqual(
            [line.attrib["data-kind"] for line in stage_four],
            ["yang", "yin", "yin"],
        )
        self.assertEqual(
            [line.attrib["data-kind"] for line in stage_five],
            ["yang", "yin", "yin", "yin", "yin", "yang"],
        )
        self.assertEqual(
            [line.attrib["data-kind"] for line in stage_six],
            ["yang", "yin", "yin", "yin", "yin", "yang"],
        )


if __name__ == "__main__":
    unittest.main()
