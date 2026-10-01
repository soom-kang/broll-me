"""Offline font declarations shared by rendered scenes and review pages."""
from __future__ import annotations

import base64
from pathlib import Path

FONTS = Path(__file__).resolve().parent / "fonts"
FONT_FILES = (
    ("Geist", "Geist-Variable.woff2", "100 900", "woff2"),
    ("Geist Mono", "GeistMono-Medium.woff2", "500", "woff2"),
    ("Noto Sans KR", "NotoSansKR.ttf", "100 900", "truetype"),
)
NOTICES = ("OFL-Geist.txt", "OFL-NotoSansKR.txt")


def shared_fonts(output_dir: str | Path) -> Path:
    """Create a portable asset directory; never replace different files or links."""
    output_dir = Path(output_dir)
    target = output_dir / "assets" / "broll-me-fonts"
    files = [filename for _, filename, _, _ in FONT_FILES] + list(NOTICES)
    # Check the complete set before copying any asset.
    for folder in (output_dir, target.parent, target):
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError(f"font asset directory must be a regular directory: {folder}")
    for filename in files:
        source, destination = FONTS / filename, target / filename
        if not source.is_file():
            raise ValueError(f"required local font or notice is missing: {source}")
        if destination.is_symlink():
            raise ValueError(f"font asset must not be a symlink: {destination}")
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != source.read_bytes()):
            raise ValueError(f"font asset differs; use a new output directory: {destination}")
    target.mkdir(parents=True, exist_ok=True)
    for filename in files:
        destination = target / filename
        if not destination.exists():
            # Exclusive creation also prevents overwriting a concurrently created file.
            with destination.open("xb") as stream:
                stream.write((FONTS / filename).read_bytes())
    return target


def font_css(output_dir: str | Path, font_mode: str = "embedded") -> str:
    if font_mode not in ("shared", "embedded"):
        raise ValueError("font_mode must be shared or embedded")
    if font_mode == "shared":
        shared_fonts(output_dir)
    declarations = []
    for family, filename, weight, format_name in FONT_FILES:
        source = FONTS / filename
        if not source.is_file():
            raise ValueError(f"required local font is missing: {source}")
        if font_mode == "shared":
            url = f"assets/broll-me-fonts/{filename}"
        else:
            mime = "ttf" if format_name == "truetype" else format_name
            encoded = base64.b64encode(source.read_bytes()).decode("ascii")
            url = f"data:font/{mime};base64,{encoded}"
        declarations.append(f"@font-face{{font-family:'{family}';src:url('{url}') format('{format_name}');font-weight:{weight};font-display:block}}")
    return "\n".join(declarations)
