"""Tables techniques fixes : sockets, consommation (TDP/TBP), graphique intégré.

Valeurs constructeur arrondies, volontairement prudentes. À compléter quand de
nouveaux modèles sortent ; chaque entrée est couverte par tests/test_specs.py.
"""
from __future__ import annotations

import re

CHIPSET_SOCKET = {
    **dict.fromkeys(["A620", "B650", "B650E", "X670", "X670E", "B840", "B850", "X870", "X870E"], "AM5"),
    **dict.fromkeys(["A520", "B450", "B550", "X470", "X570"], "AM4"),
    **dict.fromkeys(["H610", "B660", "H670", "Z690", "B760", "H770", "Z790"], "LGA1700"),
    **dict.fromkeys(["H810", "B860", "Z890"], "LGA1851"),
}

GPU_TDP = {
    "RTX 3050": 130, "RTX 3060": 170, "RTX 3060 Ti": 200, "RTX 3070": 220, "RTX 3070 Ti": 290,
    "RTX 3080": 320, "RTX 3080 Ti": 350, "RTX 3090": 350, "RTX 3090 Ti": 450,
    "RTX 4060": 115, "RTX 4060 Ti": 160, "RTX 4070": 200, "RTX 4070 Super": 220,
    "RTX 4070 Ti": 285, "RTX 4070 Ti Super": 285, "RTX 4080": 320, "RTX 4080 Super": 320,
    "RTX 4090": 450,
    "RTX 5050": 130, "RTX 5060": 145, "RTX 5060 Ti": 180, "RTX 5070": 250, "RTX 5070 Ti": 300,
    "RTX 5080": 360, "RTX 5090": 575,
    "RX 580": 185, "RX 590": 225, "RX 6500 XT": 107, "RX 6600": 132, "RX 6600 XT": 160,
    "RX 6650 XT": 180, "RX 6700 XT": 230, "RX 6750 XT": 250, "RX 6800": 250, "RX 6800 XT": 300,
    "RX 6900 XT": 300, "RX 6950 XT": 335, "RX 7600": 165, "RX 7600 XT": 190, "RX 7700 XT": 245,
    "RX 7800 XT": 263, "RX 7900 GRE": 260, "RX 7900 XT": 315, "RX 7900 XTX": 355,
    "RX 9060 XT": 160, "RX 9070": 220, "RX 9070 GRE": 220, "RX 9070 XT": 304,
    "Arc A750": 225, "Arc A770": 225, "Arc B570": 150, "Arc B580": 190,
}

# TDP constructeur des Ryzen « X » courants (la règle générique sert de repli).
RYZEN_TDP = {
    "5600X": 65, "5700X": 65, "5800X": 105, "5900X": 105, "5950X": 105,
    "7600X": 105, "7700X": 105, "7900X": 170, "7950X": 170,
    "9600X": 65, "9700X": 65, "9900X": 120, "9950X": 170,
    "7900X3D": 120, "7950X3D": 120, "9900X3D": 120, "9950X3D": 170,
}

_RYZEN = re.compile(r"^CPU:Ryzen ([3579]) (\d)(\d{3})(X3D|XT|X|G|F)?$")
_CORE = re.compile(r"^CPU:Core i([3579])-(\d{2})(\d{3})([KFST]*)$")
_ULTRA = re.compile(r"^CPU:Core Ultra ([579]) (2\d{2})([KF]*)$")


def chipset_socket(chipset: str) -> str | None:
    return CHIPSET_SOCKET.get((chipset or "").upper())


def socket_ddr(socket: str | None) -> int | None:
    return {"AM5": 5, "LGA1851": 5, "AM4": 4}.get(socket or "")


def cpu_socket(model: str) -> str | None:
    if m := _RYZEN.match(model or ""):
        return "AM5" if int(m.group(2)) >= 7 else "AM4"
    if m := _CORE.match(model or ""):
        return "LGA1700" if m.group(2) in ("12", "13", "14") else None
    if _ULTRA.match(model or ""):
        return "LGA1851"
    return None


def cpu_tdp(model: str) -> int | None:
    if m := _RYZEN.match(model or ""):
        tier, series, suffix = int(m.group(1)), int(m.group(2)), m.group(4) or ""
        exact = RYZEN_TDP.get(f"{m.group(2)}{m.group(3)}{suffix}")
        if exact:
            return exact
        if suffix == "X3D":
            return 120
        if suffix in ("X", "XT"):
            if tier == 9:
                return 170
            return 105 if tier == 7 or series == 7 else 65
        return 65
    if m := _CORE.match(model or ""):
        if m.group(2) not in ("12", "13", "14"):
            return None
        if "K" in m.group(4):
            return {9: 253, 7: 253, 5: 181, 3: 89}[int(m.group(1))]
        return 65
    if m := _ULTRA.match(model or ""):
        return 250 if "K" in m.group(3) else 65
    return None


def cpu_igpu(model: str) -> bool | None:
    if m := _RYZEN.match(model or ""):
        suffix = m.group(4) or ""
        if suffix == "F":
            return False
        if int(m.group(2)) < 7:
            return suffix == "G"
        return True
    if m := _CORE.match(model or ""):
        return None if m.group(2) not in ("12", "13", "14") else "F" not in m.group(4)
    if m := _ULTRA.match(model or ""):
        return "F" not in m.group(3)
    return None


def gpu_tdp(model: str) -> int | None:
    return GPU_TDP.get((model or "").removeprefix("GPU:"))
