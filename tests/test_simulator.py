import random
import unittest

from systolic_lab.reference import matmul
from systolic_lab.simulator import Config, simulate, synthetic


class SimulatorTests(unittest.TestCase):
    def test_known_product_and_exact_clock_schedule(self):
        a, b = [[1, 2, 3], [4, 5, 6]], [[7, 8], [9, 10], [11, 12]]
        data = simulate(a, b, Config(2, 2, 8, 1), trace=True)
        self.assertEqual(data["result"], [[58, 64], [139, 154]])
        self.assertEqual(data["metrics"]["total_cycles"], 11)
        self.assertEqual(data["metrics"]["load_cycles"], 3)
        self.assertEqual(data["metrics"]["compute_cycles"], 5)
        self.assertEqual(data["metrics"]["store_cycles"], 3)
        wave = [f for f in data["frames"] if f["phase"] == "compute"]
        self.assertEqual([f["active_macs"] for f in wave], [1, 3, 4, 3, 1])
        self.assertEqual(wave[1]["cells"][0][1]["acc"], 8)
        self.assertEqual(wave[2]["cells"][1][1]["acc"], 32)
        self.assertEqual(data["metrics"]["link_bytes"], 12)

    def test_registered_transport_and_reduction_index(self):
        a, b = synthetic(3, 5, 4, 8)
        data = simulate(a, b, Config(3, 4), trace=True)
        wave = [f for f in data["frames"] if f["phase"] == "compute"]
        for tick, frame in enumerate(wave):
            for i, row in enumerate(frame["cells"]):
                for j, cell in enumerate(row):
                    k = tick - i - j
                    self.assertEqual(cell["active"], 0 <= k < 5)
                    if cell["active"]:
                        self.assertEqual(cell["k"], k)
                        self.assertEqual((cell["a"], cell["b"]), (a[i][k], b[k][j]))
                    if tick and j:
                        self.assertEqual(cell["a"], wave[tick - 1]["cells"][i][j - 1]["a"])
                    if tick and i:
                        self.assertEqual(cell["b"], wave[tick - 1]["cells"][i - 1][j]["b"])

    def test_ragged_tiles_no_padding_traffic(self):
        a, b = synthetic(5, 7, 3, 7)
        data = simulate(a, b, Config(4, 4, 16, 2), trace=True)
        self.assertEqual(data["result"], matmul(a, b))
        m = data["metrics"]
        self.assertEqual(m["tile_count"], 2)
        self.assertEqual(m["useful_macs"], 105)
        self.assertEqual(m["load_bytes"], 77)
        self.assertEqual(m["store_bytes"], 60)
        self.assertEqual(m["compute_cycles"], 21)
        self.assertEqual(m["total_cycles"], 39)
        self.assertEqual(m["link_bytes"], 133)
        self.assertEqual(m["masked_pe_cycles"], 165)
        for frame in data["frames"]:
            for row in frame["cells"]:
                for cell in row:
                    if cell["masked"]:
                        self.assertFalse(cell["active"])
                        self.assertIsNone(cell["a"])
                        self.assertIsNone(cell["b"])
                        self.assertEqual(cell["acc"], 0)

    def test_240_seeded_random_shapes_and_rectangular_arrays(self):
        rng = random.Random(2026)
        for case in range(240):
            m, k, n = [rng.randint(1, 9) for _ in range(3)]
            config = Config(rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 32), rng.randint(0, 4))
            a, b = synthetic(m, k, n, case)
            with self.subTest(case=case, shape=(m, k, n), config=config):
                data = simulate(a, b, config)
                stats = data["metrics"]
                self.assertEqual(data["result"], matmul(a, b))
                self.assertEqual(stats["useful_macs"], m * n * k)
                self.assertEqual(stats["store_bytes"], 4 * m * n)
                # Independently derived traffic from row/column tile counts.
                self.assertEqual(stats["load_bytes"], m * k * ((n + config.cols - 1) // config.cols)
                                 + k * n * ((m + config.rows - 1) // config.rows))
                self.assertEqual(stats["scratchpad_reads"], stats["load_bytes"])
                self.assertLessEqual(stats["overall_utilization"], stats["compute_utilization"])

    def test_zero_operands_still_count_scheduled_macs(self):
        data = simulate([[0, 0]], [[0], [0]], Config(3, 2), trace=True)
        self.assertEqual(data["result"], [[0]])
        self.assertEqual(data["metrics"]["useful_macs"], 2)
        self.assertEqual(data["metrics"]["compute_cycles"], 2)

    def test_int8_extremes_fit_int32(self):
        data = simulate([[-128] * 128], [[-128] for _ in range(128)], Config(1, 1))
        self.assertEqual(data["result"], [[2_097_152]])
        self.assertEqual(simulate([[127, -128]], [[-128], [127]])["result"], [[-32512]])

    def test_bandwidth_affects_only_transfer_cycles(self):
        a, b = synthetic(8, 8, 8)
        slow = simulate(a, b, Config(4, 4, 1, 2), trace=True)
        fast = simulate(a, b, Config(4, 4, 64, 2), trace=True)
        self.assertGreater(slow["metrics"]["total_cycles"], fast["metrics"]["total_cycles"])
        for key in ("compute_cycles", "useful_macs", "external_bytes", "link_bytes"):
            self.assertEqual(slow["metrics"][key], fast["metrics"][key])
        self.assertEqual(slow["result"], fast["result"])
        for run in (slow, fast):
            for tile in run["tiles"]:
                for phase in ("load", "store"):
                    frames = [f for f in run["frames"] if f["tile"] == tile["id"] and f["phase"] == phase]
                    self.assertEqual(sum(f["transfer_bytes"] for f in frames), tile[phase + "_bytes"])
                    self.assertEqual([f["transfer_bytes"] for f in frames[:2]], [0, 0])
                    self.assertTrue(all(f["transfer_bytes"] <= run["config"]["bandwidth"] for f in frames))

    def test_scratchpad_boundary_rejects_oversized_tile(self):
        a, b = synthetic(2, 3, 2)
        with self.assertRaisesRegex(ValueError, "tile needs 12"):
            simulate(a, b, Config(2, 2, scratchpad=11))
        self.assertTrue(simulate(a, b, Config(2, 2, scratchpad=12))["verified"])

    def test_invalid_inputs_and_configuration(self):
        for a, b in [([], [[1]]), ([[1], [2, 3]], [[1]]), ([[1, 2]], [[1]]),
                     ([[1.5]], [[1]]), ([[True]], [[1]]), ([[128]], [[1]]),
                     ([[1]], [[-129]]), ("bad", [[1]])]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                simulate(a, b)
        for config in (Config(rows=0), Config(cols=17), Config(bandwidth=0),
                       Config(latency=-1), Config(scratchpad=0), Config(rows=True)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                simulate([[1]], [[1]], config)
        with self.assertRaises(ValueError):
            synthetic(0, 2, 2)

    def test_summary_and_trace_are_identical_and_repeatable(self):
        a, b = synthetic(5, 7, 3)
        summary = simulate(a, b)
        traced = simulate(a, b, trace=True)
        self.assertEqual(summary["result"], traced["result"])
        self.assertEqual(summary["metrics"], traced["metrics"])
        self.assertEqual(traced, simulate(a, b, trace=True))
        self.assertEqual(len(traced["frames"]), traced["metrics"]["total_cycles"])
        self.assertEqual([f["cycle"] for f in traced["frames"]], list(range(1, len(traced["frames"]) + 1)))

    def test_trace_resource_limit_does_not_limit_summary(self):
        a, b = synthetic(128, 1, 128)
        with self.assertRaisesRegex(ValueError, "trace would exceed"):
            simulate(a, b, Config(1, 1), trace=True)
        self.assertTrue(simulate(a, b, Config(1, 1))["verified"])
        with self.assertRaisesRegex(ValueError, "PE states"):
            simulate([[1]], [[1]], Config(16, 16, latency=1024), trace=True)
        self.assertTrue(simulate([[1]], [[1]], Config(16, 16, latency=1024))["verified"])


if __name__ == "__main__":
    unittest.main()
