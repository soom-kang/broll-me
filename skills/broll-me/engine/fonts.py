"""Offline font declarations shared by rendered scenes and review pages."""
from __future__ import annotations

import base64
import html
from pathlib import Path
import sys

FONTS = Path(__file__).resolve().parent / "fonts"
FONT_FILES = (
    ("Geist", "Geist-Variable.woff2", "100 900", "woff2"),
    ("Geist Mono", "GeistMono-Medium.woff2", "500", "woff2"),
    ("Noto Sans KR", "NotoSansKR.ttf", "100 900", "truetype"),
)
NOTICES = ("OFL-Geist.txt", "OFL-NotoSansKR.txt")
FONT_ASSETS = tuple(filename for _, filename, _, _ in FONT_FILES) + NOTICES


def font_notices() -> list[tuple[str, str]]:
    """Read the required notices before copying or embedding any font assets."""
    notices = []
    for filename in NOTICES:
        source = FONTS / filename
        if not source.is_file():
            raise ValueError(f"required local font notice is missing: {source}")
        text = source.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"required local font notice is empty: {source}")
        notices.append((filename, text))
    return notices


def validate_shared_fonts(output_dir: str | Path) -> Path:
    """Check all shared font sources and destinations without creating assets."""
    font_notices()
    output_dir = Path(output_dir)
    target = output_dir / "assets" / "broll-me-fonts"
    absolute = target.absolute()
    for folder in (absolute, *absolute.parents):
        standard_alias = (sys.platform == "darwin" and folder in {Path("/tmp"), Path("/var")}
                          and folder.resolve() == Path("/private") / folder.name)
        if (folder.is_symlink() and not standard_alias) or (folder.exists() and not folder.is_dir()):
            raise ValueError(f"font asset directory must be a regular directory: {folder}")
    for filename in FONT_ASSETS:
        source, destination = FONTS / filename, target / filename
        if not source.is_file():
            raise ValueError(f"required local font or notice is missing: {source}")
        if destination.is_symlink():
            raise ValueError(f"font asset must not be a symlink: {destination}")
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != source.read_bytes()):
            raise ValueError(f"font asset differs; use a new output directory: {destination}")
    return target


def shared_fonts(output_dir: str | Path) -> Path:
    """Create a portable asset directory; never replace different files or links."""
    target = validate_shared_fonts(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename in FONT_ASSETS:
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
    if font_mode == "embedded":
        for filename, text in font_notices():
            # CSS is inserted into HTML <style> raw text. Entities keep either
            # parser from ending the notice early and can be decoded losslessly.
            safe_text = html.escape(text, quote=False).replace("*/", "*&#47;")
            declarations.append(f"/* Font notice: {filename}\n{safe_text}\n*/")
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
