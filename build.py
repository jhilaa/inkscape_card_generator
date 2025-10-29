#!/usr/bin/env python3
import os, subprocess, xml.etree.ElementTree as ET, yaml

BASE_DIR  = os.path.abspath(os.path.dirname(__file__))
OUT_DIR   = os.path.join(BASE_DIR, "out")
os.makedirs(OUT_DIR, exist_ok=True)

def qname(ns, tag): return f"{{{ns}}}{tag}"

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def replace_node_with(root, target, newnode):
    for parent in root.iter():
        kids = list(parent)
        for i, c in enumerate(kids):
            if c is target:
                parent.remove(c)
                parent.insert(i, newnode)
                return True
    return False

def main():
    meta = load_yaml(os.path.join(BASE_DIR, "meta.yml"))

    tpl_path = os.path.join(BASE_DIR, meta["template"])
    tree = ET.parse(tpl_path)
    root = tree.getroot()

    # Namespaces
    SVG_NS = root.tag.split("}")[0].strip("{") if "}" in root.tag else "http://www.w3.org/2000/svg"
    # Recherche du rect slot (pas besoin d’XPath compliqué)
    title_rect = None
    for el in root.iter():
        if el.get("id") == "title_slot":
            title_rect = el
            break
    if title_rect is None or not title_rect.tag.endswith("rect"):
        raise RuntimeError("template.svg : <rect id='title_slot'> introuvable.")

    # Dimensions du slot
    x = float(title_rect.get("x", "0"))
    y = float(title_rect.get("y", "0"))
    w = float(title_rect.get("width", "0"))
    h = float(title_rect.get("height", "0"))

    # Paramètres style
    font_family = meta.get("title_font_family", "DejaVu Sans")
    font_size   = float(meta.get("title_font_size", 36))
    fill_color  = meta.get("title_fill", "#222")
    padding     = float(meta.get("title_padding", 8))
    line_height = float(meta.get("line_height", 1.2))

    # Lecture du texte
    title_file = os.path.join(BASE_DIR, meta["title_file"])
    with open(title_file, "r", encoding="utf-8") as f:
        text_content = f.read().rstrip("\n")

    # Création du <text> (haut-gauche du slot + padding)
    text_el = ET.Element(qname(SVG_NS, "text"), {
        "x": str(x + padding),
        # baseline : on place la première ligne à y + padding + font_size
        "y": str(y + padding + font_size),
        "fill": fill_color,
        "font-family": font_family,
        "font-size": str(font_size),
        "xml:space": "preserve"
    })

    # Gestion des lignes (si le .txt contient des sauts de ligne)
    lines = text_content.split("\n") if text_content else [""]
    for i, line in enumerate(lines):
        tspan = ET.SubElement(text_el, qname(SVG_NS, "tspan"), {
            "x": str(x + padding),
            "dy": str(font_size * (line_height if i > 0 else 0))  # 0 pour la première ligne
        })
        tspan.text = line

    # Remplace le rect par le texte (on enlève le cadre)
    replace_node_with(root, title_rect, text_el)

    # Sauvegarde SVG
    out_svg = os.path.join(OUT_DIR, f"{meta.get('id','card')}.svg")
    tree.write(out_svg, encoding="utf-8", xml_declaration=True)
    print("SVG:", out_svg)

    # Export PNG avec Inkscape (si présent dans le PATH)
    out_png = os.path.join(OUT_DIR, f"{meta.get('id','card')}.png")
    png_w   = int(meta.get("export_png_width", 1600))
    subprocess.run([
        os.environ.get("INKSCAPE_EXE", "inkscape"),
        out_svg,
        "--export-type=png",
        f"--export-filename={out_png}",
        f"--export-width={png_w}"
    ], check=True)
    print("PNG:", out_png)

if __name__ == "__main__":
    main()
