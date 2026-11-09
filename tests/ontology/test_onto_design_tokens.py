"""T22: design tokens meet the contrast and colour-blindness rules, and nothing bypasses them.

- WCAG AA: text >= 4.5:1 on every surface it is drawn on; kind colours, the accent and the
  severity colours >= 3:1 against --bg, and a badge's --bg symbol >= 3:1 on its colour.
- The kind palette stays distinguishable (CIEDE2000) under protanopia, deuteranopia and
  tritanopia simulation (Machado et al. 2009, full severity), in both themes.
- No raw colour, size, spacing or timing literal in app.css or the view's JS.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from ontotest import SKILL_DIR

HTML = SKILL_DIR / "assets" / "html"
TOKENS = (HTML / "tokens.css").read_text(encoding="utf-8")
KINDS = [f"--kind-{i}" for i in range(1, 9)]
MIN_DELTA_E = {"normal": 15.0, "protanopia": 10.0, "deuteranopia": 10.0, "tritanopia": 10.0}


def _block(pattern: str) -> dict[str, str]:
    match = re.search(pattern + r"\s*\{(.*?)\n\s*\}", TOKENS, flags=re.S | re.M)
    assert match, pattern
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", match.group(1)))


LIGHT = _block(r"^:root")
DARK_MEDIA = _block(r":root:not\(\[data-theme=\"light\"\]\)")
DARK = {**LIGHT, **_block(r"^:root\[data-theme=\"dark\"\]")}
THEMES = {"light": LIGHT, "dark": DARK}


def _rgb(hex_colour: str) -> list[int]:
    return [int(hex_colour[i : i + 2], 16) for i in (1, 3, 5)]


def _linear(channel: float) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    r, g, b = (_linear(c) for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# --- Contrast ---------------------------------------------------------------------------------


def test_dark_blocks_are_in_sync() -> None:
    """The OS-preference dark block and the forced [data-theme="dark"] block hold the same values."""
    assert _block(r"^:root\[data-theme=\"dark\"\]") == DARK_MEDIA


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("text", ["--text", "--text-muted", "--text-faint"])
@pytest.mark.parametrize("surface", ["--bg", "--surface", "--surface-raised"])
def test_text_contrast(theme: str, text: str, surface: str) -> None:
    t = THEMES[theme]
    assert contrast(t[text], t[surface]) >= 4.5, f"{text} on {surface} ({theme})"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("token", [*KINDS, "--kind-fallback", "--accent", "--error", "--warn", "--info"])
def test_non_text_contrast(theme: str, token: str) -> None:
    t = THEMES[theme]
    assert contrast(t[token], t["--bg"]) >= 3.0, f"{token} against --bg ({theme})"


# --- Colour blindness ------------------------------------------------------------------------

SIMULATIONS = {
    "normal": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _lab(hex_colour: str, matrix) -> tuple[float, float, float]:
    v = [_linear(c) for c in _rgb(hex_colour)]
    r, g, b = (max(0.0, min(1.0, sum(row[j] * v[j] for j in range(3)))) for row in matrix)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    (l1, a1, b1), (l2, a2, b2) = lab1, lab2
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dh = 0.0 if c1p * c2p == 0 else (h2p - h1p + 180) % 360 - 180
    d_l, d_c = l2 - l1, c2p - c1p
    d_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    l_bar, c_bar_p = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) > 180:
        h_bar = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    else:
        h_bar = (h1p + h2p) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    d_theta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(c_bar_p**7 / (c_bar_p**7 + 25**7))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c
    return math.sqrt((d_l / s_l) ** 2 + (d_c / s_c) ** 2 + (d_h / s_h) ** 2 + r_t * (d_c / s_c) * (d_h / s_h))


def test_ciede2000_reference_pair() -> None:
    """Sharma et al. (2005) test data, pair 1."""
    assert ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)) == pytest.approx(2.0425, abs=1e-4)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("vision", SIMULATIONS)
def test_kind_palette_stays_distinguishable(theme: str, vision: str) -> None:
    labs = [_lab(THEMES[theme][k], SIMULATIONS[vision]) for k in KINDS]
    worst = min(
        (ciede2000(labs[i], labs[j]), KINDS[i], KINDS[j]) for i in range(len(KINDS)) for j in range(i + 1, len(KINDS))
    )
    assert worst[0] >= MIN_DELTA_E[vision], f"{worst[1]} and {worst[2]} under {vision} ({theme}): {worst[0]:.1f}"


# --- No raw literals outside tokens.css ------------------------------------------------------

RAW = re.compile(
    r"#[0-9a-fA-F]{3,8}\b(?![-\w])"  # hex colour
    r"|\b(?:rgb|rgba|hsl|hsla|oklch|lab)\("  # colour functions
    r"|(?<![\w.$-])\d*\.?\d+(?:px|em|rem|ms|s|pt|vw)\b"  # lengths and durations (100vh is layout)
)
VIEW_FILES = ["app.css", "app.js", "graph-model.js", "graph-view.js", "pane.js"]


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:])//.*$", r"\1", text)


@pytest.mark.parametrize("name", VIEW_FILES)
def test_no_raw_style_literals(name: str) -> None:
    text = _strip_comments((HTML / name).read_text(encoding="utf-8"))
    found = [m.group(0) for m in RAW.finditer(text)]
    assert found == [], f"{name} uses raw values {found}; add a token to tokens.css instead"


def test_the_lint_catches_raw_values() -> None:
    for sample in ["color: #fff;", "padding: 4px;", "transition: opacity 150ms;", "fill: rgb(0, 0, 0);", "x = '12px'"]:
        assert RAW.search(sample), sample
    for sample in ["height: 100vh;", "width: 100%;", "var(--space-2)", "href = `#${id}`", "scale(0.5)"]:
        assert not RAW.search(sample), sample


def test_every_token_used_is_defined() -> None:
    defined = set(re.findall(r"(--[\w-]+):", TOKENS))
    for name in VIEW_FILES:
        text = (HTML / name).read_text(encoding="utf-8")
        used = set(re.findall(r"var\((--[\w-]+)\)", text)) | set(re.findall(r'"(--[\w-]+)"', text))
        used -= {"--k"}  # set per kind slot in app.css
        assert used <= defined, f"{name} uses undefined tokens: {sorted(used - defined)}"


def test_reduced_motion_zeroes_durations() -> None:
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", TOKENS, flags=re.S)
    assert block and "--duration-fast: 0ms" in block.group(1)


def test_tokens_file_exists_once() -> None:
    assert sorted(p.name for p in Path(HTML).glob("*.css")) == ["app.css", "tokens.css"]
