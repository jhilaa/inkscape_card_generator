#!/usr/bin/env python3
# build.py - prototype builder (texte, couleurs, image, LaTeX, export PNG)
import os, csv, re, base64, mimetypes, tempfile, subprocess
import xml.etree.ElementTree as ET

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_SVG = os.path.join(BASE_DIR, "template.svg")
CSV_FILE     = os.path.join(BASE_DIR, "cards.csv")
OUT_DIR      = os.path.join(BASE_DIR, "out")
os.makedirs(OUT_DIR, exist_ok=True)

# Exports
EXPORT_PNG = True      # <- PNG auto avec Inkscape
PNG_WIDTH  = 1200      # px (garde le ratio)

# Alignement des formules
FORMULA_ALIGN = {
    "formula1_slot": "left",
    "formula2_slot": "center",
}

# LaTeX wrapper pour dvisvgm (DVI -> SVG)
STANDALONE_TEX = r"""\documentclass[12pt]{standalone}
\usepackage{amsmath,amssymb}
\begin{document}
$%s$
\end{document}
"""

# Namespaces
ns = {
    "svg": "http://www.w3.org/2000/svg",
    "xlink": "http://www.w3.org/1999/xlink",
}
ET.register_namespace("", ns["svg"])
ET.register_namespace("xlink", ns["xlink"])

def q(tag): return f"{{{ns['svg']}}}{tag}"

# -------- util long/units --------
def _parse_length(val):
    if val is None: return None
    s = str(val).strip()
    if not s or s.endswith("%"): return None
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$", s)
    if not m: return None
    v = float(m.group(1)); u = m.group(2).lower()
    if u in ("", "px"): return v
    if u == "pt": return v * (96.0/72.0)
    if u == "in": return v * 96.0
    if u == "cm": return v * (96.0/2.54)
    if u == "mm": return v * (96.0/25.4)
    return None

def read_size_origin(svg_root):
    vb = svg_root.get("viewBox")
    if vb:
        p = [t for t in vb.replace(",", " ").split() if t]
        if len(p) == 4:
            ox, oy, w, h = map(float, p)
            return ox, oy, w, h
    w = _parse_length(svg_root.get("width")) or 1.0
    h = _parse_length(svg_root.get("height")) or 1.0
    return 0.0, 0.0, w, h

# -------- LaTeX -> SVG (DVI) --------
def latex_to_svg(math_src: str, workdir: str) -> str:
    tex = os.path.join(workdir, "f.tex")
    dvi = os.path.join(workdir, "f.dvi")
    svg = os.path.join(workdir, "f.svg")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(STANDALONE_TEX % math_src)
    subprocess.run(["latex", "-interaction=nonstopmode", "f.tex"], cwd=workdir, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["dvisvgm", "--no-fonts", "--exact", "--verbosity=0", "--optimize=none",
                    "-o", "f.svg", "f.dvi"], cwd=workdir, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return svg

# -------- Template ops --------
def rect_bbox(rect):
    return (float(rect.get("x","0")), float(rect.get("y","0")),
            float(rect.get("width")), float(rect.get("height")))

def ensure_defs(root):
    defs = root.find("svg:defs", ns)
    if defs is None:
        defs = ET.Element(q("defs")); root.insert(0, defs)
    return defs

def merge_defs_with_prefix(template_defs, foreign_root, prefix):
    defs = foreign_root.find("svg:defs", ns)
    if defs is None: return
    for child in list(defs):
        c = ET.fromstring(ET.tostring(child, encoding="utf-8"))
        for e in c.iter():
            _id = e.get("id")
            if _id: e.set("id", prefix+_id)
            for attr in ("{http://www.w3.org/1999/xlink}href", "href"):
                v = e.get(attr)
                if v and v.startswith("#"):
                    e.set(attr, "#"+prefix+v[1:])
        template_defs.append(c)

def place_group_in_slot(root, slot_rect, foreign_root, group_id, align="center", margin=0.06):
    # size/origin de la formule
    ox, oy, fw, fh = read_size_origin(foreign_root)
    # bbox du slot
    x, y, w, h = rect_bbox(slot_rect)
    # scale pour rentrer
    scale = min((w*(1-2*margin))/fw, (h*(1-2*margin))/fh)
    if scale <= 0: scale = 1.0
    # x selon align
    left_tx   = x - ox*scale + (w*margin)
    center_tx = x + (w - fw*scale)/2 - ox*scale
    right_tx  = x + (w - fw*scale) - ox*scale - (w*margin)
    if   align == "left":  tx = left_tx
    elif align == "right": tx = right_tx
    else:                  tx = center_tx
    # y centré verticalement
    ty = y + (h - fh*scale)/2 - oy*scale
    g = ET.Element(q("g"), {"id": group_id, "transform": f"translate({tx},{ty}) scale({scale})"})
    # copier enfants (sans defs) en préfixant les href vers defs
    prefix = group_id + "__"
    for child in list(foreign_root):
        if child.tag.endswith("defs"): continue
        clone = ET.fromstring(ET.tostring(child, encoding="utf-8"))
        for e in clone.iter():
            for attr in ("{http://www.w3.org/1999/xlink}href", "href"):
                v = e.get(attr)
                if v and v.startswith("#"):
                    e.set(attr, "#"+prefix+v[1:])
        g.append(clone)
    return g, prefix

def replace_node_with(parent_root, target, newnode):
    # remplace target par newnode dans le parent
    for p in parent_root.iter():
        kids = list(p)
        for i, c in enumerate(kids):
            if c is target:
                p.remove(c)
                p.insert(i, newnode)
                return True
    return False

def inject_text(root, slot_rect, content, color="#222222", font="Times, Georgia, serif", size=60, align="left"):
    x, y, w, h = rect_bbox(slot_rect)
    # marges
    mx = 0.04 * w
    my = 0.25 * h
    # point d'ancrage selon align
    if align == "left":
        anchor="start"; tx = x + mx
    elif align == "right":
        anchor="end";   tx = x + w - mx
    else:
        anchor="middle"; tx = x + w/2
    ty = y + my + size  # baseline
    text = ET.Element(q("text"), {
        "x": f"{tx}", "y": f"{ty}",
        "fill": color, "font-family": font, "font-size": str(size),
        "text-anchor": anchor
    })
    # \n pour multi-ligne
    for i, line in enumerate(str(content).split("\\n")):
        t = ET.SubElement(text, q("tspan"), {"x": f"{tx}", "dy": "0" if i==0 else str(size*1.25)})
        t.text = line
    return text

def embed_image_as_data_uri(path):
    b = open(path, "rb").read()
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(b).decode("ascii")

def inject_image(root, slot_rect, img_path):
    x, y, w, h = rect_bbox(slot_rect)
    href = embed_image_as_data_uri(img_path)
    # On place l'image “plein cadre” et on demande au moteur de rendu de préserver le ratio
    img = ET.Element(q("image"), {
        "{http://www.w3.org/1999/xlink}href": href,
        "x": str(x), "y": str(y),
        "width": str(w), "height": str(h),
        "preserveAspectRatio": "xMidYMid meet"
    })
    return img

# -------- build --------
def build_card(row):
    # parse template
    tree = ET.parse(TEMPLATE_SVG); root = tree.getroot()
    defs = ensure_defs(root)

    # Couleurs globales
    bg_color    = (row.get("bg_color") or "").strip() or None
    frame_color = (row.get("frame_color") or "").strip() or None
    text_color  = (row.get("text_color") or "").strip() or "#222222"

    bg = root.find(".//*[@id='bg']")
    if bg_color and bg is not None:
        bg.set("fill", bg_color)
    frame = root.find(".//*[@id='frame']")
    if frame_color and frame is not None:
        frame.set("stroke", frame_color)

    # Titre
    title = (row.get("title") or "").strip()
    title_rect = root.find(".//*[@id='title_slot']")
    if title and title_rect is not None:
        title_node = inject_text(root, title_rect, title, color=text_color, font="Times, Georgia, serif", size=64, align="left")
        replace_node_with(root, title_rect, title_node)

    # Image
    img_path = (row.get("image") or "").strip()
    img_rect = root.find(".//*[@id='image_slot']")
    if img_path and img_rect is not None and os.path.isfile(os.path.join(BASE_DIR, img_path)):
        node = inject_image(root, img_rect, os.path.join(BASE_DIR, img_path))
        replace_node_with(root, img_rect, node)
    elif img_rect is not None:
        # si pas d'image, on supprime juste la bordure du slot pour faire propre
        img_rect.set("stroke", "none")

    # Formules
    with tempfile.TemporaryDirectory() as tmp:
        for col, sid in [("formula1","formula1_slot"), ("formula2","formula2_slot")]:
            expr = (row.get(col) or "").strip()
            slot_rect = root.find(f".//*[@id='{sid}']")
            if slot_rect is None:
                continue
            if not expr:
                # pas de formule -> enlever le slot visuel
                replace_node_with(root, slot_rect, ET.Element(q("g"), {"id": sid+"_empty"}))
                continue
            # latex -> svg
            svg_path = latex_to_svg(expr, tmp)
            f_tree = ET.parse(svg_path); f_root = f_tree.getroot()
            # merge defs d'abord (avec préfixes)
            group_id = sid + "_content"
            merge_defs_with_prefix(defs, f_root, group_id + "__")
            # créer le groupe placé/scalé
            g, _ = place_group_in_slot(root, slot_rect, f_root, group_id, align=FORMULA_ALIGN.get(sid,"center"), margin=0.06)
            replace_node_with(root, slot_rect, g)

    return tree

def main():
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f, delimiter=";")
        for row in rdr:
            cid = (row.get("id") or "000").strip()
            out_svg = os.path.join(OUT_DIR, f"{cid}.svg")
            tree = build_card(row)
            tree.write(out_svg, encoding="utf-8", xml_declaration=True)
            print("SVG:", out_svg)

            if EXPORT_PNG:
                out_png = os.path.join(OUT_DIR, f"{cid}.png")
                subprocess.run([
                    "inkscape", out_svg, "--export-type=png",
                    f"--export-filename={out_png}",
                    f"--export-width={PNG_WIDTH}"
                ], check=True)
                print("PNG:", out_png)

if __name__ == "__main__":
    main()
