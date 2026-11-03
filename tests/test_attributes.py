import unittest

from composants_watch.normalize import apply, attributes, normalize
from tests.helpers import make_listing


def attrs_of(title):
    cat, model = normalize(title)
    return attributes(cat, model, title)


class AttributesTest(unittest.TestCase):
    def test_cpu(self):
        self.assertEqual(attrs_of("AMD Ryzen 7 7800X3D"), {"socket": "AM5", "tdp_w": 120, "igpu": True})
        self.assertEqual(attrs_of("Intel Core i5-12400F"), {"socket": "LGA1700", "tdp_w": 65, "igpu": False})

    def test_mb(self):
        cases = {
            "MSI MAG B650 Tomahawk WiFi": {"socket": "AM5", "ddr": 5},
            "Carte mère MSI MAG B650 Tomahawk WiFi ATX": {"socket": "AM5", "ddr": 5, "form": "ATX"},
            "ASRock B650M Pro RS": {"socket": "AM5", "ddr": 5, "form": "mATX"},
            "Gigabyte B650I Aorus Ultra": {"socket": "AM5", "ddr": 5, "form": "ITX"},
            "ASUS ROG Strix B650-I Gaming WiFi": {"socket": "AM5", "ddr": 5, "form": "ITX"},
            "MSI PRO B760M-A DDR4": {"socket": "LGA1700", "ddr": 4, "form": "mATX"},
            "ASUS TUF Z790-Plus WiFi D4": {"socket": "LGA1700", "ddr": 4},
            "MSI Z790 Tomahawk": {"socket": "LGA1700"},
            "ASRock B550 Phantom Gaming 4": {"socket": "AM4", "ddr": 4},
            "Carte mère Gigabyte B550M DS3H micro-ATX": {"socket": "AM4", "ddr": 4, "form": "mATX"},
        }
        for title, want in cases.items():
            with self.subTest(title=title):
                self.assertEqual(attrs_of(title), want)

    def test_ram_gpu_psu(self):
        self.assertEqual(attrs_of("G.Skill 2x16GB DDR5-6000 CL36"), {"ddr": 5})
        self.assertEqual(attrs_of("MSI RTX 4070 SUPER Ventus"), {"tdp_w": 220})
        self.assertEqual(attrs_of("Gigabyte RTX 9999"), {})
        self.assertEqual(attrs_of("Alimentation Corsair RM850x 850W 80+ Gold"), {"watts": 850})

    def test_cooler(self):
        self.assertEqual(attrs_of("Ventirad Thermalright Peerless Assassin 120 SE - AM4/AM5/LGA1700"),
                         {"type": "air", "sockets": ["AM4", "AM5", "LGA1700"]})
        a = attrs_of("Ventirad Cooler Master V4 ALPHA 3DHP (AM4, AM5 LGA 1700 / 1200 / 115x-)")
        self.assertEqual(a["sockets"], ["AM4", "AM5", "LGA1200", "LGA1700"])
        a = attrs_of("Ventirad Noctua NH-U12A LGA1700/1851")
        self.assertEqual(a["sockets"], ["LGA1700", "LGA1851"])
        self.assertEqual(attrs_of("Ventirad be quiet! Pure Rock 3 - Noir"), {"type": "air"})
        self.assertEqual(attrs_of("Watercooling AIO Arctic Liquid Freezer III 360"), {"type": "aio"})

    def test_case_mon_kbd(self):
        self.assertEqual(attrs_of("Boîtier micro-ATX Jonsbo D31"), {"max_form": "mATX"})
        self.assertEqual(attrs_of("Boîtier PC DeepCool CG530 WH Blanc"), {})
        self.assertEqual(attrs_of('Écran PC 27" MSI MAG 274QP - WQHD, 240Hz'),
                         {"inches": 27, "res": "QHD", "hz": 240})
        self.assertEqual(attrs_of("Clavier mécanique Keychron K8 TKL"),
                         {"type": "Mécanique", "layout": "TKL"})

    def test_unrecognised_empty(self):
        self.assertEqual(attributes(None, None, "Souris"), {})

    def test_apply_fills_attrs(self):
        li = apply(make_listing(title="AMD Ryzen 7 7800X3D", category=None, model=None))
        self.assertEqual(li.attrs["socket"], "AM5")
        li = apply(make_listing(title="Souris gamer", category=None, model=None))
        self.assertEqual(li.attrs, {})


if __name__ == "__main__":
    unittest.main()
