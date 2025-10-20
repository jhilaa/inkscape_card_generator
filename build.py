#!/usr/bin/env python3
# build.py - prototype builder (fix align + origin of dvisvgm SVGs)
import csv, os, subprocess, tempfile, xml.etree.ElementTree as ET, re, shutil

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_SVG = os.path.join(BASE_DIR, "template.svg")
CSV_FILE = os.path.join(BASE_DIR, "cards.csv")
OUT_DIR = os.path.join(BASE_DIR, "out")
os.makedirs(OUT_DIR, exist_ok=True)

ns = {
    "svg": "http://www.w3.org/2000/svg",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}
ET.register_namespace("", ns["svg"])
ET.register_namespace("inkscape", ns["inkscape"])
ET.register_namespace("sodipodi", ns["sodipodi"])
ET.register_namespace("xlink", ns["xlink"])

STANDALONE_TEX = r"""\documentclass[12pt]{standalone}
\usepackage{amsmath,amssymb}
\begin{document}
$%s$
\end{document}
"""

def _parse_length(val: str):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("%"):
        return None
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$", s)
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ("", "px"):
        return v
    if unit == "pt":
        return v * (96.0/72.0)
    if unit == "in":
        return v * 96.0
    if unit == "cm":
        return v * (96.0/2.54)
    if unit == "mm":
        return v * (96.0/25.4)
    return None

def read_svg_size_and_origin(svg_root):
    """
    Returns (origin_x, origin_y, width, height)
    Prefer viewBox if present (handles negative origin), else width/height fallback.
    """
    vb = svg_root.get("viewBox")
    if vb:
        parts = [p for p in vb.replace(",", " ").split() if p]
        if len(parts) == 4:
            ox, oy, w, h = map(float, parts)
            return ox, oy, w, h
    # fallback to width/height attributes
    w = _parse_length(svg_root.get("width"))
    h = _parse_length(svg_root.get("height"))
    if w is None or h is None or w == 0 or h == 0:
        # last resort: use 1x1 to avoid division by zero
        return 0.0, 0.0, float(w or 1.0), float(h or 1.0)
    return 0.0, 0.0, float(w), float(h)

def generate_formula_svg(latex_math, workdir):
    tex = os.path.join(workdir, "f.tex")
    dvi = os.path.join(workdir, "f.dvi")
    svg = os.path.join(workdir, "f.svg")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(STANDALONE_TEX % latex_math)
    # compile DVI
    subprocess.run(["latex", "-interaction=nonstopmode", "f.tex"], cwd=workdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # dvi -> svg (vector paths)
    subprocess.run(["dvisvgm", "--no-fonts", "--exact", "--verbosity=0", "--optimize=none", "-o", "f.svg", "f.dvi"], cwd=workdir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return svg

def qname(tag):
    return f"{{{ns['svg']}}}{tag}"

def bbox_from_rect(rect):
    x = float(rect.get("x", "0"))
    y = float(rect.get("y", "0"))
    w = float(rect.get("width"))
    h = float(rect.get("height"))
    return x, y, w, h

def import_formula_into_template(template_path, slots_dict, out_path, align_map=None):
    """
    align_map: dict slot_id -> 'left'|'center'|'right'
    """
    if align_map is None:
        align_map = {}
    tree = ET.parse(template_path)
    root = tree.getroot()
    # prepare defs in template
    template_defs = root.find("svg:defs", ns)
    if template_defs is None:
        template_defs = ET.Element(qname("defs"))
        root.insert(0, template_defs)
    for slot_id, svg_path in slots_dict.items():
        slot_elem = root.find(f".//*[@id='{slot_id}']")
        if slot_elem is None:
            slot_elem = root.find(f".//*[@inkscape:label='{slot_id}']", ns)
        if slot_elem is None:
            print("Warning: slot not found in template:", slot_id)
            continue
        # compute bbox from rect
        if slot_elem.tag == qname("rect"):
            x,y,w,h = bbox_from_rect(slot_elem)
        else:
            rect = slot_elem.find(".//svg:rect", ns)
            if rect is None:
                raise RuntimeError(f"Slot {slot_id}: ajoute un rectangle dimensionné dedans.")
            x,y,w,h = bbox_from_rect(rect)
        # load formula svg
        f_tree = ET.parse(svg_path)
        f_root = f_tree.getroot()
        # read origin and size (viewBox preferred)
        origin_x, origin_y, fw, fh = read_svg_size_and_origin(f_root)
        # ensure positive fw/fh
        if fw == 0 or fh == 0:
            fw = fw or 1.0
            fh = fh or 1.0
        # prefix defs and ids to avoid collisions
        prefix = f"{slot_id}__"
        formula_defs = f_root.find("svg:defs", ns)
        if formula_defs is not None:
            for child in list(formula_defs):
                s = ET.tostring(child, encoding="utf-8")
                clone = ET.fromstring(s)
                for e in clone.iter():
                    _id = e.get("id")
                    if _id:
                        e.set("id", prefix + _id)
                    for attr in ("{http://www.w3.org/1999/xlink}href", "href"):
                        v = e.get(attr)
                        if v and v.startswith("#"):
                            e.set(attr, "#" + prefix + v[1:])
                template_defs.append(clone)
        # compute scale to fit into slot with margin
        margin = 0.06
        # note: fw,fh are formula bbox width/height according to dvisvgm viewBox
        scale = min((w*(1-2*margin))/fw, (h*(1-2*margin))/fh)
        if scale <= 0:
            scale = 1.0
        # default horizontal alignment
        align = align_map.get(slot_id, "center")
        # compute tx,ty accounting for origin (we must shift by -origin*scale)
        # compute base left position and center position
        left_tx = x - origin_x*scale + (w*margin)  # left with small left margin
        center_tx = x + (w - fw*scale)/2 - origin_x*scale
        right_tx = x + (w - fw*scale) - origin_x*scale - (w*margin)  # right with right margin
        if align == "left":
            tx = left_tx
        elif align == "right":
            tx = right_tx
        else:
            tx = center_tx
        # vertical: center inside slot
        ty = y + (h - fh*scale)/2 - origin_y*scale
        # build wrapper group
        g = ET.Element(qname("g"), {"id": f"{slot_id}_content", "transform": f"translate({tx},{ty}) scale({scale})"})
        # copy children excluding defs (they were merged) and prefix xlink:href in uses
        for child in list(f_root):
            if child.tag.endswith("defs"):
                continue
            s = ET.tostring(child, encoding="utf-8")
            clone = ET.fromstring(s)
            for e in clone.iter():
                for attr in ("{http://www.w3.org/1999/xlink}href", "href"):
                    v = e.get(attr)
                    if v and v.startswith("#"):
                        e.set(attr, "#" + prefix + v[1:])
            g.append(clone)
        # replace slot rect with the group (find and replace in parent)
        parent = None
        for p in root.iter():
            for i, c in enumerate(list(p)):
                if c is slot_elem:
                    p.remove(slot_elem)
                    p.insert(i, g)
                    parent = p
                    break
            if parent is not None:
                break
    tree.write(out_path, encoding="utf-8", xml_declaration=True)

def build_all():
    # define alignment map here (prototype choices)
    align_map = {
        "formula1_slot": "left",   # top slot -> left aligned
        "formula2_slot": "center", # bottom slot -> centered
    }
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            cid = row.get("id") or "000"
            slots = {}
            with tempfile.TemporaryDirectory() as tmp:
                for col, sid in [("formula1","formula1_slot"), ("formula2","formula2_slot")]:
                    expr = (row.get(col) or "").strip()
                    if not expr:
                        continue
                    svg_formula = generate_formula_svg(expr, tmp)
                    slots[sid] = svg_formula
                out_svg = os.path.join(OUT_DIR, f"{cid}.svg")
                import_formula_into_template(TEMPLATE_SVG, slots, out_svg, align_map=align_map)
                print("Wrote", out_svg)

if __name__ == "__main__":
    build_all()
