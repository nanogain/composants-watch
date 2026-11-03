import unittest

from composants_watch.specs import (chipset_socket, cpu_igpu, cpu_socket, cpu_tdp, gpu_tdp,
                                    socket_ddr)
from tests.helpers import make_listing


class SpecsTest(unittest.TestCase):
    def check(self, fn, cases):
        for arg, want in cases.items():
            with self.subTest(fn=fn.__name__, arg=arg):
                self.assertEqual(fn(arg), want)

    def test_cpu_socket(self):
        self.check(cpu_socket, {
            "CPU:Ryzen 7 7800X3D": "AM5", "CPU:Ryzen 5 9600X": "AM5", "CPU:Ryzen 5 8600G": "AM5",
            "CPU:Ryzen 5 5600X": "AM4", "CPU:Ryzen 7 5800X3D": "AM4", "CPU:Core i5-13600KF": "LGA1700",
            "CPU:Core i3-12100F": "LGA1700", "CPU:Core Ultra 7 265K": "LGA1851",
            "CPU:Core i7-9700K": None, "GPU:RTX 4070": None})

    def test_cpu_tdp(self):
        self.check(cpu_tdp, {
            "CPU:Ryzen 7 7800X3D": 120, "CPU:Ryzen 9 9950X": 170, "CPU:Ryzen 5 7600": 65,
            "CPU:Core i9-14900K": 253, "CPU:Core i5-13600KF": 181, "CPU:Core i5-12400F": 65,
            "CPU:Core Ultra 7 265K": 250, "CPU:Core Ultra 5 245": 65, "CPU:Core i7-9700K": None,
            "CPU:Ryzen 7 9700X": 65, "CPU:Ryzen 5 9600X": 65, "CPU:Ryzen 7 5700X": 65, "CPU:Ryzen 7 5800X": 105,
            "CPU:Ryzen 7 7700X": 105, "CPU:Ryzen 9 9900X": 120, "CPU:Ryzen 9 9950X3D": 170,
            "CPU:Ryzen 9 7950X3D": 120, "CPU:Ryzen 7 9800X3D": 120})

    def test_cpu_igpu(self):
        self.check(cpu_igpu, {
            "CPU:Ryzen 5 7600F": False, "CPU:Core i5-13600KF": False, "CPU:Core i5-12400F": False,
            "CPU:Ryzen 5 5600X": False, "CPU:Ryzen 5 5600G": True, "CPU:Ryzen 7 7800X3D": True,
            "CPU:Core Ultra 5 245K": True, "CPU:Core Ultra 5 245KF": False, "CPU:Core i7-9700K": None})

    def test_chipset_socket(self):
        self.check(chipset_socket, {
            "B650": "AM5", "B650E": "AM5", "X870E": "AM5", "A620": "AM5", "B550": "AM4", "A520": "AM4",
            "B760": "LGA1700", "Z790": "LGA1700", "H610": "LGA1700", "B860": "LGA1851", "Z890": "LGA1851",
            "H150": None})

    def test_gpu_tdp(self):
        self.check(gpu_tdp, {
            "GPU:RTX 4070 Super": 220, "GPU:RTX 5090": 575, "GPU:RX 9070 XT": 304, "GPU:RX 580": 185,
            "GPU:Arc B580": 190, "GPU:RTX 9999": None})

    def test_every_gpu_in_table_has_positive_tdp(self):
        from composants_watch.specs import GPU_TDP
        self.assertTrue(all(v > 0 for v in GPU_TDP.values()))
        self.assertGreaterEqual(len(GPU_TDP), 40)

    def test_socket_ddr(self):
        self.check(socket_ddr, {"AM5": 5, "LGA1851": 5, "AM4": 4, "LGA1700": None, None: None})

    def test_listing_attrs_default(self):
        a, b = make_listing(), make_listing()
        self.assertEqual(a.attrs, {})
        a.attrs["x"] = 1
        self.assertEqual(b.attrs, {})


if __name__ == "__main__":
    unittest.main()
