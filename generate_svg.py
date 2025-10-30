import os
import yaml
from lxml import etree

try:
    import cairosvg
    CAIRO_AVAILABLE = True
except ImportError:
    CAIRO_AVAILABLE = False


# ----------------------------
# Fonction utilitaire : insérer du texte avec retour à la ligne
# ----------------------------
def insert_wrapped_text(parent, x, y, width, text, font_size=32, line_height=1.2):
    """
    Ajoute un élément <text> avec des <tspan> pour gérer le retour à la ligne.
    Approche simple basée sur une largeur moyenne de caractère.
    """
    import textwrap

    avg_char_width = font_size * 0.6  # heuristique monospace-like
    max_chars = max(1, int(width / avg_char_width))

    # Découper texte en lignes (préserve paragraphes)
    lines = []
    for para in text.split("\n"):
        if para.strip() == "":
            lines.append("")  # ligne vide pour un saut
        else:
            lines.extend(textwrap.wrap(para, width=max_chars))

    text_elem = etree.Element(
        "text",
        x=str(x),
        y=str(y),
        style=f"font-size:{font_size}px; font-family:Arial; fill:#000000",
    )

    first_line = True
    for line in lines:
        dy = "0em" if first_line else f"{line_height}em"
        tspan = etree.SubElement(text_elem, "tspan", x=str(x), dy=dy)
        tspan.text = line
        first_line = False

    parent.append(text_elem)


def ensure_out_dir(path="out"):
    os.makedirs(path, exist_ok=True)
    return path


def export_png_with_cairosvg(svg_path, png_path, scale=1.0):
    if not CAIRO_AVAILABLE:
        raise RuntimeError(
            "CairoSVG n'est pas installé. Installe-le avec: pip install cairosvg\n"
            "Ou utilise l'export Inkscape CLI (voir plus bas)."
        )
    # scale permet d'augmenter la résolution si besoin (ex: 2.0 pour @2x)
    cairosvg.svg2png(url=svg_path, write_to=png_path, scale=scale)


def export_png_with_inkscape(svg_path, png_path, dpi=300):
    """
    Alternative: Inkscape CLI (assure une fidélité parfaite à Inkscape).
    Nécessite Inkscape installé et disponible dans le PATH.
    """
    import subprocess
    cmd = [
        "inkscape",
        f"--export-type=png",
        f"--export-filename={png_path}",
        f"--export-dpi={dpi}",
        svg_path,
    ]
    subprocess.run(cmd, check=True)


def main():
    # 1) Dossier de sortie
    out_dir = ensure_out_dir("out")
    out_svg = os.path.join(out_dir, "output.svg")
    out_png = os.path.join(out_dir, "output.png")

    # 2) Charger config YAML
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 3) Charger le template SVG
    tree = etree.parse("template.svg")
    root = tree.getroot()

    ns = {"svg": "http://www.w3.org/2000/svg"}

    # 4) Insérer le titre
    title_slot = root.xpath('//*[@id="title_slot"]', namespaces=ns)[0]
    x = float(title_slot.get("x")) + 10
    y = float(title_slot.get("y")) + 40
    w = float(title_slot.get("width"))
    insert_wrapped_text(root, x, y, w, config.get("title", ""), font_size=48)

    # 5) Insérer text1
    text1_slot = root.xpath('//*[@id="text1_slot"]', namespaces=ns)[0]
    x = float(text1_slot.get("x")) + 10
    y = float(text1_slot.get("y")) + 40
    w = float(text1_slot.get("width"))
    insert_wrapped_text(root, x, y, w, config.get("text1", ""), font_size=28)

    # 6) Insérer text2
    text2_slot = root.xpath('//*[@id="text2_slot"]', namespaces=ns)[0]
    x = float(text2_slot.get("x")) + 10
    y = float(text2_slot.get("y")) + 40
    w = float(text2_slot.get("width"))
    insert_wrapped_text(root, x, y, w, config.get("text2", ""), font_size=28)

    # 7) Sauvegarder le SVG
    tree.write(out_svg, encoding="utf-8", xml_declaration=True, pretty_print=True)
    print(f"SVG généré: {out_svg}")

    # 8) Exporter en PNG
    try:
        export_png_with_cairosvg(out_svg, out_png, scale=1.0)
        print(f"PNG exporté (CairoSVG): {out_png}")
    except Exception as e:
        print("Export PNG via CairoSVG indisponible ou en erreur:", e)
        print("Tentative d'export via Inkscape CLI…")
        export_png_with_inkscape(out_svg, out_png, dpi=300)
        print(f"PNG exporté (Inkscape): {out_png}")


if __name__ == "__main__":
    main()
