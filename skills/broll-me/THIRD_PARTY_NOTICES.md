# Third-party notices

Preserve these notices with redistributed copies of `broll-me`.

- Software: MIT copyright and permission text remains in [LICENSE](LICENSE).
- Geist and Geist Mono: SIL Open Font License; see [OFL-Geist.txt](engine/fonts/OFL-Geist.txt).
- Noto Sans KR: SIL Open Font License; see [OFL-NotoSansKR.txt](engine/fonts/OFL-NotoSansKR.txt) and [font revision](reference/provenance.md#fonts-and-runtime).
- Lucide icon path data: ISC license; see [Lucide-LICENSE.txt](licenses/Lucide-LICENSE.txt).

Generated HTML in `embedded` font mode includes the full Geist and Noto Sans KR OFL notices in named CSS comments. Read them in the HTML source; they do not add visible page content. In `shared` mode, keep the adjacent `assets/broll-me-fonts/` directory with the HTML, including its two OFL files. Both modes reject missing or empty source notices before copying or embedding fonts.

Embedded fonts do not include referenced media, custom assets or their licenses. Include those files and applicable notices separately when redistributing an output.

Install Playwright, Chromium and NumPy in a separate runtime; their distributions are outside this archive. `skill-creator` supports local development packaging and is not a runtime dependency.

[Palette references](reference/provenance.md#palette-references) describe the chosen color values. Private brand boards, logos, photographs and footage stay outside the package. A supplied video asset does not grant automatic redistribution rights.
