import unittest

from composants_watch.normalize import normalize

CASES = [
    # GPU (titres réels Dealabs / Reddit + FR)
    ("Carte graphique MSI GeForce RTX 4070 SUPER Ventus 2X 12G", ("GPU", "GPU:RTX 4070 Super")),
    ("Gigabyte RTX 4060 Ti 16 Go", ("GPU", "GPU:RTX 4060 Ti")),
    ("Carte graphique PNY RTX 5070 Ti Triple Fan", ("GPU", "GPU:RTX 5070 Ti")),
    ("RTX 5070 Ti", ("GPU", "GPU:RTX 5070 Ti")),
    ("Sapphire Pulse Radeon RX 7800 XT", ("GPU", "GPU:RX 7800 XT")),
    ("RX 7900 XTX Nitro+", ("GPU", "GPU:RX 7900 XTX")),
    ("Carte Graphique MLLSE AMD Radeon RX 580 - 8 Go, 2048SP, GDDR5", ("GPU", "GPU:RX 580")),
    ("Carte graphique XFX RX 9070 XT - 16GB, GDDR6", ("GPU", "GPU:RX 9070 XT")),
    ("Carte graphique AMD RX 9070 ASRock Challenger 16 Go", ("GPU", "GPU:RX 9070")),
    ("Carte graphique PowerColor Reaper AMD Radeon RX 9060 XT 16GB", ("GPU", "GPU:RX 9060 XT")),
    ("Carte graphique Soyo RTX 3070 - 8 Go", ("GPU", "GPU:RTX 3070")),
    ("Carte Graphique Nvidia Geforce MLLSE RTX 3070 8 Go - 8 Broches", ("GPU", "GPU:RTX 3070")),
    ("ASUS Dual GeForce RTX 5060 8GB", ("GPU", "GPU:RTX 5060")),
    ("Zotac RTX 5090 Solid", ("GPU", "GPU:RTX 5090")),
    ("Intel Arc B580 Limited Edition 12 Go", ("GPU", "GPU:Arc B580")),
    ("[GPU] Gigabyte GeForce RTX 5070 WINDFORCE - $549", ("GPU", "GPU:RTX 5070")),
    ("Carte graphique 5060 Ti Gigabyte - Stand fnac", ("GPU", "GPU:RTX 5060 Ti")),
    # CPU
    ("AMD Ryzen 7 7800X3D", ("CPU", "CPU:Ryzen 7 7800X3D")),
    ("Processeur AMD Ryzen 5 7600 (3.8 GHz)", ("CPU", "CPU:Ryzen 5 7600")),
    ("Ryzen 9 9950X3D", ("CPU", "CPU:Ryzen 9 9950X3D")),
    ("AMD Ryzen 5 5600X", ("CPU", "CPU:Ryzen 5 5600X")),
    ("Intel Core i5-13600KF", ("CPU", "CPU:Core i5-13600KF")),
    ("Processeur Intel Core i7 14700K", ("CPU", "CPU:Core i7-14700K")),
    ("Intel Core Ultra 7 265K", ("CPU", "CPU:Core Ultra 7 265K")),
    ("Intel Core Ultra 5 245KF", ("CPU", "CPU:Core Ultra 5 245KF")),
    # RAM
    ("Kit Corsair Vengeance 32 Go (2 x 16 Go) DDR5 6000 MHz CL30", ("RAM", "RAM:DDR5-32Go-6000")),
    ("G.Skill 2x16GB DDR5-6000 CL36", ("RAM", "RAM:DDR5-32Go-6000")),
    ("[RAM] Corsair SHUGO 2x16GB DDR5-6000 CL28 Memory Kit - $556.99", ("RAM", "RAM:DDR5-32Go-6000")),
    ("Crucial 16 Go DDR4 3200", ("RAM", "RAM:DDR4-16Go-3200")),
    ("Kingston Fury Beast 64 Go (2x32Go) DDR5 5600MHz", ("RAM", "RAM:DDR5-64Go-5600")),
    ("Mémoire RAM Patriot 32Go DDR4 3600 MHz", ("RAM", "RAM:DDR4-32Go-3600")),
    # SSD
    ("Samsung 990 Pro 2 To NVMe M.2", ("SSD", "SSD:NVMe-2To")),
    ("SSD Crucial MX500 1TB SATA", ("SSD", "SSD:SATA-1To")),
    ("SSD WD Black SN770 500 Go", ("SSD", "SSD:NVMe-500Go")),
    ("SSD interne Lexar NM790 4 To M.2 PCIe 4.0", ("SSD", "SSD:NVMe-4To")),
    ("Samsung 870 EVO 1000 Go SATA", ("SSD", "SSD:SATA-1To")),
    # Carte mère
    ("MSI MAG B650 Tomahawk WiFi", ("MB", "MB:B650")),
    ("Carte mère ASUS ROG Strix Z790-E Gaming", ("MB", "MB:Z790")),
    ("Gigabyte X870E Aorus Master", ("MB", "MB:X870E")),
    ("ASRock B550M Pro4", ("MB", "MB:B550")),
    # Alimentation
    ("Alimentation Corsair RM850x 850W 80+ Gold", ("PSU", "PSU:850W-Gold")),
    ("Alimentation be quiet! Pure Power 12 M 750W 80 PLUS Gold", ("PSU", "PSU:750W-Gold")),
    ("Seasonic Focus GX-1000 1000W Platinum", ("PSU", "PSU:1000W-Platinum")),
    # Non composants / exclusions
    ("Souris gamer Logitech G502", (None, None)),
    ("Câble HDMI 2.1 2m", (None, None)),
    ("PC portable Lenovo Legion RTX 4060", (None, None)),
    ("[Prebuilt] Powerspec G536 - 12gb 5070, 32gb ram, 7500x3D", (None, None)),
    ("PC Gamer Ryzen 7 7800X3D RTX 4070 Super", (None, None)),
    ("Boîtier PC MSI MPG Velox 100R - Support Vertical pour Carte Graphique", (None, None)),
    ("[Controller] PowerA Enhanced Wireless Controller - $24.99", (None, None)),
    ("Waterblock EK pour RTX 4080", (None, None)),
    ("Câble HDMI 2.1 compatible RTX 4090", (None, None)),
    ("Jeu Battlefield offert pour l'achat d'une RTX 5070", (None, None)),
    ("Jeux offerts pour l'achat d'un Ryzen 7 9800X3D", (None, None)),
    ("Ordinateur Lenovo Legion T5 RTX 4070 Ryzen 7 7700", (None, None)),
    ("Mini PC Minisforum AtomMan G7 RTX 4060", (None, None)),
    ("MacBook Pro M3 18Go 512Go SSD", (None, None)),
    ("Mac mini M4 16Go 512Go SSD", (None, None)),
    ("SSD externe Samsung T7 1 To", (None, None)),
    ("SanDisk Extreme Portable SSD 2 To", (None, None)),
    ("Alimentation be quiet! 850W Gold compatible ATX 3.1", ("PSU", "PSU:850W-Gold")),
    ("PC de bureau Phoenix - Ryzen 7 7800X3D, RTX 3090 24 Go (occasion)", (None, None)),
    ("[Prebuilt] iBUYPOWER Element Gaming PC Desktop — AMD Ryzen 7 9800X3D", (None, None)),
    ("Carte graphique Radeon 9060 XT GAMING OC Ice 16Go V1 Blanc", ("GPU", "GPU:RX 9060 XT")),
    ("Carte Graphique Palit RTX3070 Jetstream V1 8GB DDR6", ("GPU", "GPU:RTX 3070")),
    ("[PSU] MSI MPG A1000GS PCIE5 II, Fully Modular Gaming 1000W Power Supply", ("PSU", "PSU:1000W")),
]


class NormalizeTest(unittest.TestCase):
    def test_table(self):
        for title, want in CASES:
            with self.subTest(title=title):
                self.assertEqual(normalize(title), want)

    def test_hint_category_kept_when_model_unknown(self):
        self.assertEqual(normalize("Barrette mystère", hint_category="RAM"), ("RAM", None))

    def test_hint_does_not_override_recognised(self):
        self.assertEqual(normalize("RTX 4070 Super", hint_category="GPU"), ("GPU", "GPU:RTX 4070 Super"))


if __name__ == "__main__":
    unittest.main()
