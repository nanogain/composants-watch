"""Reconnaissance déterministe catégorie + modèle canonique à partir d'un titre.

Règles ordonnées : exclusions (PC complets, portables, boîtiers…), puis GPU, CPU,
RAM, SSD, carte mère, alimentation. Un titre non reconnu donne (hint, None).
"""
from __future__ import annotations

import re

from .models import Listing

_I = re.IGNORECASE

EXCLUDE = re.compile(
    r"pc\s*portable|laptop|notebook|pc\s*gamer|pc\s*fixe|pc\s*de\s*bureau|\bdesktop\b|"
    r"gaming\s*pc|\bprebuilt\b|ordinateur|mini\s*pc|macbook|mac\s*mini|\bimac\b|"
    r"\bexterne\b|\bportable\b|waterblock|backplate|\briser\b|c[aâ]ble|"
    r"pour\s*l.achat|[àa]\s*l.achat|compatible\s+(?:avec\s+)?(?:les?\s+)?(?:rtx|rx|gtx|geforce|radeon|ryzen|core)|"
    r"\btour\b|\bcontroller\b|\bmanette\b|\bconsole\b", _I)

# Exclusions fortes, testées AVANT le nom de produit en tête de titre.
HARD_EXCLUDE = re.compile(
    r"smartphone|serrure|smartlock|cylindre|carte\s*de\s*capture|^\s*s[ée]lection|"
    r"pack\s*combo|\bcombo\b|\bsouris\b|\bcasque\b", _I)

# Nom de produit en tête de titre (après d'éventuels tags [Prime], [Fnac+]…).
_LEAD = re.compile(r"^\s*((?:\[[^\]]*\]\s*)*)(.*)$", re.S)
_TAG_CAT = {"MONITOR": "MON", "KEYBOARD": "KBD", "COOLER": "COOL", "CASE": "CASE"}
_NOUN = [
    ("MON", re.compile(r"^(?:[ée]cran|moniteur|monitor)\b", _I)),
    ("KBD", re.compile(r"^(?:clavier|keyboard)\b", _I)),
    ("COOL", re.compile(r"^(?:ventirad|refroidisseur|kit\s*watercooling|watercooling|aio\b|cpu\s*cooler)", _I)),
    ("CASE", re.compile(r"^bo[iî]tier", _I)),
]

MON_SIZE = re.compile(r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:\"|''|”|“|″|pouces\b|inch)", _I)
MON_RES = [
    ("UWQHD", re.compile(r"3440\s*[x×]\s*1440|uwqhd", _I)),
    ("DQHD", re.compile(r"5120\s*[x×]\s*1440|dual\s*qhd|\bdqhd\b", _I)),
    ("UWFHD", re.compile(r"2560\s*[x×]\s*1080|uwfhd", _I)),
    ("UHD", re.compile(r"3840\s*[x×]\s*2160|\b4k\b|\buhd\b", _I)),
    ("QHD", re.compile(r"2560\s*[x×]\s*1440|\bw?qhd\b|1440p", _I)),
    ("FHD", re.compile(r"1920\s*[x×]\s*1080|full\s*hd|\bfhd\b|1080p", _I)),
]
MON_HZ = re.compile(r"\b(\d{2,3})\s*hz\b", _I)

KBD_MECH = re.compile(r"m[ée]cani|mechanical|magn[ée]tique|hall\s*effect|\bhe\b|switch", _I)
KBD_PCT = re.compile(r"\b(60|65|75)\s*%")
KBD_TKL = re.compile(r"\btkl\b|tenkeyless|\b80\s*%", _I)

COOL_AIO = re.compile(r"\baio\b|watercooling|water\s*cooling|liquid|nautilus|kraken", _I)
COOL_RAD = re.compile(r"\b(120|240|280|360|420)\s*(?:mm)?\b", _I)

CASE_ATX = re.compile(r"(?<![\w-])e-?atx\b|(?<![\w-])atx\b", _I)
CASE_MATX = re.compile(r"micro-?atx|\bm-?atx\b", _I)
CASE_TOWER = re.compile(r"moyen[\s-]*tour|mid[\s-]*tower|midi[\s-]*tower|\bmi-tour|grand[\s-]*tour|full[\s-]*tower", _I)
CASE_ITX = re.compile(r"itx", _I)

GPU_RTX = re.compile(r"\brtx\s*([2-5]0[5-9]0)(\s*ti)?(\s*super)?\b", _I)
GPU_BARE = re.compile(r"\b((?:30|40|50)[5-9]0)(\s*ti)?(\s*super)?\b", _I)
GPU_CTX = re.compile(r"carte\s*graphique|geforce|\bgpu\b", _I)
GPU_RX = re.compile(r"\b(?:rx|radeon)\s*([5-9]\d{2,3})(?:\s*(xtx|xt|gre))?\b", _I)
GPU_ARC = re.compile(r"\barc\s*([ab]\d{3})\b", _I)

CPU_RYZEN = re.compile(r"\bryzen\s*([3579])\s*(\d{4})(x3d|xt|x|g|f)?\b", _I)
CPU_CORE = re.compile(r"\bcore\s*i([3579])[\s-]*(\d{4,5})([kfst]*)\b", _I)
CPU_ULTRA = re.compile(r"\bcore\s*ultra\s*([579])\s*(\d{3})([kf]*)\b", _I)

RAM_DDR = re.compile(r"(?<![g])ddr([45])", _I)
RAM_KIT = re.compile(r"\b(\d)\s*x\s*(\d{1,3})\s*(?:go|gb)\b", _I)
RAM_CAP = re.compile(r"\b(\d{1,3})\s*(?:go|gb)\b", _I)
RAM_FREQ = re.compile(r"(?<![g])ddr[45][\s-]*(\d{4})\b|\b(\d{4})\s*mhz", _I)

SSD_CTX = re.compile(r"\bssd\b|nvme|m\.2|pcie|\bsn\d{3}\b|\b9[89]0\s*pro\b|\b870\s*evo\b|"
                     r"\bmx500\b|\bnm\d{3}\b", _I)
SSD_TB = re.compile(r"\b(\d+)\s*(?:to|tb)\b", _I)
SSD_GB = re.compile(r"\b(\d{3,4})\s*(?:go|gb)\b", _I)

MB_CTX = re.compile(r"carte\s*m[eè]re|motherboard|\bmobo\b", _I)
MB_CHIP = re.compile(r"\b([bhxz]\d{3}e?)m?\b", _I)
MB_CHIP_A = re.compile(r"\b(a[56]20)m?\b", _I)

PSU_W = re.compile(r"\b(\d{3,4})\s*w\b", _I)
PSU_CERT = re.compile(r"\b(bronze|silver|gold|platinum|titanium)\b", _I)
PSU_CTX = re.compile(r"alimentation|\bpsu\b|80\s*\+|80\s*plus", _I)


def _gpu(t: str) -> str | None:
    m = GPU_RTX.search(t) or (GPU_CTX.search(t) and GPU_BARE.search(t))
    if not m and GPU_BARE.search(t):
        b = GPU_BARE.search(t)
        if b.group(2) or b.group(3):
            m = b
    if m:
        suffix = "".join(s for s, g in ((" Ti", m.group(2)), (" Super", m.group(3))) if g)
        return f"GPU:RTX {m.group(1)}{suffix}"
    m = GPU_RX.search(t)
    if m:
        return f"GPU:RX {m.group(1)}" + (f" {m.group(2).upper()}" if m.group(2) else "")
    m = GPU_ARC.search(t)
    if m:
        return f"GPU:Arc {m.group(1).upper()}"
    return None


def _cpu(t: str) -> str | None:
    m = CPU_RYZEN.search(t)
    if m:
        return f"CPU:Ryzen {m.group(1)} {m.group(2)}{(m.group(3) or '').upper()}"
    m = CPU_ULTRA.search(t)
    if m:
        return f"CPU:Core Ultra {m.group(1)} {m.group(2)}{m.group(3).upper()}"
    m = CPU_CORE.search(t)
    if m:
        return f"CPU:Core i{m.group(1)}-{m.group(2)}{m.group(3).upper()}"
    return None


def _ram(t: str) -> tuple[bool, str | None]:
    d = RAM_DDR.search(t)
    if not d:
        return False, None
    k = RAM_KIT.search(t)
    if k:
        cap = int(k.group(1)) * int(k.group(2))
    else:
        c = RAM_CAP.search(t)
        cap = int(c.group(1)) if c else None
    f = RAM_FREQ.search(t)
    freq = (f.group(1) or f.group(2)) if f else None
    if not cap or not freq:
        return True, None
    return True, f"RAM:DDR{d.group(1)}-{cap}Go-{freq}"


def _ssd(t: str) -> tuple[bool, str | None]:
    if not SSD_CTX.search(t):
        return False, None
    m = SSD_TB.search(t)
    if m:
        cap = f"{int(m.group(1))}To"
    else:
        g = SSD_GB.search(t)
        if not g:
            return True, None
        gb = int(g.group(1))
        cap = f"{gb // 1000}To" if gb >= 1000 and gb % 1000 == 0 else f"{gb}Go"
    iface = "SATA" if re.search(r"\bsata\b", t, _I) else "NVMe"
    return True, f"SSD:{iface}-{cap}"


def _mb(t: str) -> str | None:
    m = MB_CHIP.search(t) or (MB_CTX.search(t) and MB_CHIP_A.search(t))
    return f"MB:{m.group(1).upper()}" if m else None


def _psu(t: str) -> str | None:
    w, cert = PSU_W.search(t), PSU_CERT.search(t)
    if not w or not (cert or PSU_CTX.search(t)):
        return None
    return f"PSU:{w.group(1)}W" + (f"-{cert.group(1).capitalize()}" if cert else "")


def _mon(t: str) -> str | None:
    size, hz = MON_SIZE.search(t), MON_HZ.search(t)
    res = next((name for name, rx in MON_RES if rx.search(t)), None)
    if not (size and hz and res):
        return None
    inches = round(float(size.group(1).replace(",", ".")))
    return f"MON:{inches}-{res}-{hz.group(1)}Hz"


def _kbd(t: str) -> str:
    kind = "Mécanique" if KBD_MECH.search(t) else "Membrane"
    pct = KBD_PCT.search(t)
    layout = pct.group(1) if pct else ("TKL" if KBD_TKL.search(t) else "Complet")
    return f"KBD:{kind}-{layout}"


def _cool(t: str) -> str | None:
    if not COOL_AIO.search(t):
        return "COOL:Air"
    rad = COOL_RAD.search(t)
    return f"COOL:AIO-{rad.group(1)}" if rad else None


def _case(t: str) -> str | None:
    if CASE_ATX.search(t):
        return "CASE:ATX"
    if CASE_MATX.search(t):
        return "CASE:mATX"
    if CASE_TOWER.search(t):
        return "CASE:ATX"
    if CASE_ITX.search(t):
        return "CASE:ITX"
    return None


_PERIPH = {"MON": _mon, "KBD": _kbd, "COOL": _cool, "CASE": _case}


def _peripheral(t: str) -> str | None:
    tags, rest = _LEAD.match(t).groups()
    for tag in re.findall(r"\[([^\]]*)\]", tags):
        if (cat := _TAG_CAT.get(tag.strip().upper())):
            return cat
    return next((cat for cat, rx in _NOUN if rx.search(rest)), None)


def normalize(title: str, hint_category: str | None = None) -> tuple[str | None, str | None]:
    t = title or ""
    if HARD_EXCLUDE.search(t):
        return None, None
    if cat := _peripheral(t):
        return cat, _PERIPH[cat](t)
    if EXCLUDE.search(t):
        return None, None
    if g := _gpu(t):
        return "GPU", g
    if c := _cpu(t):
        return "CPU", c
    is_ram, r = _ram(t)
    if r:
        return "RAM", r
    is_ssd, s = _ssd(t)
    if s:
        return "SSD", s
    if p := _psu(t):
        return "PSU", p
    if m := _mb(t):
        return "MB", m
    if is_ram:
        return "RAM", None
    if is_ssd:
        return "SSD", None
    return hint_category, None


def apply(listing: Listing) -> Listing:
    listing.category, listing.model = normalize(listing.title, listing.category)
    return listing
