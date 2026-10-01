"""Compile a small SceneSpec into the existing deterministic fragment format."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

TEMPLATES = ("card", "terminal", "chart", "panel")
COMMON = {"schema_version", "template", "title", "subtitle", "width", "height", "duration", "center"}


def _text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"SceneSpec {name} must be a nonempty string")
    return value


def _number(value, name: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"SceneSpec {name} must be a finite number >= {minimum}")
    return value


def validate_scene(data: dict) -> dict:
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise ValueError("SceneSpec schema_version must be 1")
    template = data.get("template")
    if template not in TEMPLATES:
        raise ValueError(f"SceneSpec template must be one of {', '.join(TEMPLATES)}")
    content_field = "lines" if template == "terminal" else "bars" if template == "chart" else "body"
    unknown = set(data) - COMMON - {content_field}
    if unknown:
        raise ValueError(f"SceneSpec unknown fields: {', '.join(sorted(unknown))}; select palette with build options")
    spec = dict(data)
    spec["title"] = _text(data.get("title"), "title")
    if "subtitle" in data:
        spec["subtitle"] = _text(data["subtitle"], "subtitle")
    for key, default in (("width", 1920), ("height", 1080)):
        value = data.get(key, default)
        if type(value) is not int or value < 2 or value > 8192 or value % 2:
            raise ValueError(f"SceneSpec {key} must be an even integer between 2 and 8192")
        spec[key] = value
    spec["duration"] = _number(data.get("duration", 6), "duration")
    if spec["duration"] <= 0:
        raise ValueError("SceneSpec duration must be positive")
    center = data.get("center", [spec["width"] / 2, spec["height"] / 2])
    if not isinstance(center, list) or len(center) != 2:
        raise ValueError("SceneSpec center must be [x, y]")
    spec["center"] = [_number(value, "center", -math.inf) for value in center]
    if content_field == "body":
        spec["body"] = _text(data.get("body"), "body")
    elif content_field == "lines":
        if not isinstance(data.get("lines"), list) or not data["lines"]:
            raise ValueError("SceneSpec lines must be a nonempty array of strings")
        spec["lines"] = [_text(line, f"lines[{index}]") for index, line in enumerate(data["lines"])]
    else:
        if not isinstance(data.get("bars"), list) or not data["bars"]:
            raise ValueError("SceneSpec bars must be a nonempty array of label/value objects")
        bars = []
        for index, bar in enumerate(data["bars"]):
            if not isinstance(bar, dict) or set(bar) != {"label", "value"}:
                raise ValueError(f"SceneSpec bars[{index}] requires exactly label and value")
            bars.append({"label": _text(bar["label"], f"bars[{index}].label"),
                         "value": _number(bar["value"], f"bars[{index}].value")})
        spec["bars"] = bars
    return spec


def load_scene(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read SceneSpec {path}: {error}") from error
    return validate_scene(data)


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def compile_scene(data: dict) -> str:
    spec = validate_scene(data)
    W, H, T = spec["width"], spec["height"], spec["duration"]
    template = spec["template"]
    w = min(W * (0.66 if template == "panel" else 0.82), H * 1.65)
    h = H * (0.58 if template == "panel" else 0.72)
    padding = min(w * 0.07, h * 0.11)
    title_size = min(w * 0.057, h * 0.115)
    copy_size = title_size * 0.57
    title_top = padding
    subtitle_top = title_top + title_size * 1.5
    content_top = subtitle_top + (copy_size * 1.8 if "subtitle" in spec else 0)
    content_height = h - content_top - padding
    ink = "inverse-ink" if template == "terminal" else "ink"
    muted = "inverse-muted" if template == "terminal" else "muted"
    escaped = lambda value: html.escape(value, quote=True)
    content = (f'<div class="tpl-title" data-broll-text>{escaped(spec["title"])}</div>'
               + (f'<div class="tpl-subtitle" data-broll-text>{escaped(spec["subtitle"])}</div>' if "subtitle" in spec else ""))
    extra = ""
    css = (f".tpl-content{{position:absolute;left:{-w/2+padding:g}px;top:0;width:{w-2*padding:g}px;color:var(--broll-{ink})}}\n"
           f".tpl-title{{position:absolute;top:{title_top:g}px;width:100%;height:{title_size*1.3:g}px;overflow:hidden;font-size:{title_size:g}px;line-height:1.3;font-weight:650;white-space:nowrap}}\n"
           f".tpl-subtitle{{position:absolute;top:{subtitle_top:g}px;width:100%;height:{copy_size*1.4:g}px;overflow:hidden;font-size:{copy_size:g}px;line-height:1.4;color:var(--broll-{muted});white-space:nowrap}}\n"
           f".tpl-body{{position:absolute;top:{content_top:g}px;width:100%;height:{content_height:g}px;overflow:hidden;white-space:pre-wrap;font-size:{copy_size:g}px;line-height:1.55}}")
    if template in ("card", "panel"):
        content += f'<div class="tpl-body" data-broll-text>{escaped(spec["body"])}</div>'
        css += ".tpl-body{border-top:2px solid var(--broll-accent);padding-top:0.5em;box-sizing:border-box}"
    elif template == "terminal":
        content += '<pre class="tpl-body mono" id="tpl-terminal" data-broll-text></pre>'
        css += ".tpl-body{margin:0;color:var(--broll-inverse-ink);border-top:2px solid var(--broll-accent);padding-top:0.5em;box-sizing:border-box}"
        text = "\n".join(spec["lines"])
        extra = (f"const terminalText={_js(text)};\n"
                 f"const templateExtra=t=>{{const u=M.clamp((t-{T*0.22:g})/{T*0.55:g});M.setText(document.getElementById('tpl-terminal'),Array.from(terminalText).slice(0,Math.floor(Array.from(terminalText).length*u)).join(''));}};\n")
    else:
        row_height = content_height / len(spec["bars"])
        font_size = min(copy_size, row_height * 0.3)
        maximum = max(bar["value"] for bar in spec["bars"]) or 1
        rows = []
        for index, bar in enumerate(spec["bars"]):
            ratio = bar["value"] / maximum
            rows.append(f'<div class="tpl-bar-row" style="top:{index*row_height:g}px">'
                        f'<div class="tpl-bar-label" data-broll-text>{escaped(bar["label"])}</div>'
                        f'<div class="tpl-bar-value" data-broll-text>{escaped(str(bar["value"]))}</div>'
                        f'<div class="tpl-track"><div class="tpl-bar" style="width:{ratio*100:g}%"></div></div></div>')
        content += f'<div class="tpl-body">{"".join(rows)}</div>'
        css += (f".tpl-bar-row{{position:absolute;width:100%;height:{row_height:g}px;font-size:{font_size:g}px}}"
                f".tpl-bar-label,.tpl-bar-value{{position:absolute;top:0;height:{font_size*1.5:g}px;line-height:1.5;overflow:hidden;white-space:nowrap}}"
                ".tpl-bar-label{left:0;width:78%}.tpl-bar-value{right:0;width:20%;text-align:right;color:var(--broll-muted)}"
                f".tpl-track{{position:absolute;left:0;right:0;top:{row_height*.5:g}px;height:{row_height*.22:g}px;border-radius:{row_height*.08:g}px;background:var(--broll-surface-alt);overflow:hidden}}"
                ".tpl-bar{height:100%;background:var(--broll-accent);transform-origin:left center}")
        extra = f"const templateExtra=t=>{{const u=M.eo((t-{T*0.24:g})/{T*0.42:g});for(const bar of document.querySelectorAll('.tpl-bar'))bar.style.transform=`scaleX(${{u}})`;}};\n"
    surface = "inverseSurface" if template == "terminal" else "surface"
    background = "null" if template == "panel" else "P.canvas"
    script = ("const P=M.palette;\n" + extra + f"M.scene({{W:{W},H:{H},T:{T:g},bg:{background},center:{_js(spec['center'])},intro:null,\n"
              f"SH:{{compact:{{w:{w*.88:g},h:{h*.82:g},r:{padding*.6:g},bg:P.{surface},cam:1}},open:{{w:{w:g},h:{h:g},r:{padding*.6:g},bg:P.{surface},cam:1}}}},\n"
              f"start:'compact',spring:[{90/T:g},0.84],SEQ:[[{T*.12:g},'open']],layers:[{{el:'tpl-layer',tin:{T*.18:g},tout:null,anchor:'t',o:{_js({'din': T*.012, 'lin': T*.05, 'lout': T*.02})}}}]"
              + (",extra:templateExtra" if extra else "") + "});")
    return (f'<title>{escaped(spec["title"])}</title>\n<style>{css}</style>\n'
            f'<div data-slot="shape"><div class="L" id="tpl-layer"><div class="tpl-content">{content}</div></div></div><!--/shape-->\n'
            f'<script>{script}</script>\n')
