import os
from lxml import etree
from latex_svg import latex_to_svg_fragment

# === Configuration ===
# latex_code = r"\frac{3}{7}"
#latex_code = r"	\sum_{k=1}^{k=6} k"
latex_code = r"	\int_{x=a}^{x=b} f(x,t)dx k"
latex_scale = 2.5
font_size = 28
svg_width = 700
svg_height = 200
x_start = 50
y_base = 100

# === Phrase avant et après la formule ===
text_before = "Le résultat de la division "
text_after = " est égal à environ 0.5."

def extract_svg_width(svg_fragment: str) -> float:
    """
    Extrait la largeur du fragment SVG LaTeX à partir du viewBox.
    Retourne 0.0 si non disponible ou erreur.
    """
    try:
        root = etree.fromstring(svg_fragment.encode("utf-8"))
        viewBox = root.get("viewBox")
        if viewBox:
            parts = [float(v) for v in viewBox.strip().split()]
            if len(parts) == 4:
                _, _, width, _ = parts
                return width
    except Exception as e:
        print(f"[debug] Erreur extraction largeur SVG : {e}")
    return 0.0

# === Génération du fragment SVG depuis LaTeX ===
svg_fragment = latex_to_svg_fragment(f"${latex_code}$", scale=latex_scale)
if not svg_fragment:
    print("❌ LaTeX non converti")
    exit()

# === Création du SVG principal ===
SVG_NS = "http://www.w3.org/2000/svg"
NSMAP = {None: SVG_NS}
root = etree.Element("svg", nsmap=NSMAP, width=str(svg_width), height=str(svg_height))

# === Ajout du texte avant ===
text_elem = etree.SubElement(root, "text", x=str(x_start), y=str(y_base), font_size=str(font_size))
text_elem.text = text_before

# === Calcul de la position du fragment SVG ===
from PIL import ImageFont
font_path = r"C:\Windows\Fonts\arial.ttf"  # adapte si besoin
font = ImageFont.truetype(font_path, size=font_size)
text_width = font.getlength(text_before)

print(f"text_before : {text_before}")

offset_x = x_start + text_width / 2 + 10 # décalage entre le début du texte et la formule
offset_y = y_base - font_size * 0.3  # alignement baseline approx.

# === Insertion du fragment SVG ===
frag_root = etree.fromstring(svg_fragment.encode("utf-8"))
g = etree.Element("g")
g.extend(list(frag_root))
g.set("transform", f"translate({offset_x},{offset_y})")
root.append(g)

# === Ajout du texte après ===
# c'est un autre offset_x qu'il faut calculer
#svg_width = 50
svg_width = extract_svg_width(svg_fragment)
text_after_elem = etree.SubElement(root, "text", x=str(offset_x + svg_width), y=str(y_base), font_size=str(font_size))
text_after_elem.text = text_after   

# === Sauvegarde ===
out_path = "out/inline_phrase.svg"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
etree.ElementTree(root).write(out_path, pretty_print=True, xml_declaration=True, encoding="utf-8")
print(f"✅ SVG généré : {out_path}")
