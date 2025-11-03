import os
import re
import yaml
from lxml import etree
from PIL import ImageFont
from latex_svg import latex_to_svg_fragment

# === Constantes ===
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_SIZE = 28
LINE_HEIGHT = 1.3
LATEX_SCALE = 2.5
BASELINE_RATIO = 0.82

SVG_NS = "http://www.w3.org/2000/svg"
NSMAP = {None: SVG_NS}

# === Regex pour découper texte + formules + espaces + sauts de ligne
PATTERN = re.compile(r"""
    (?P<newline>\n)
  | (?P<formula>
        \$\$(?:(?!\$\$).)*\$\$
      | \\

\[(?:(?!\\\]

).)*\\\]


      | (?<!\\)\$(?:(?!\$(?!\d)).)*?(?<!\\)\$
      | \\\((?:(?!\\\)).)*\\\)
    )
  | (?P<word>[^\s]+[ \t]*)
""", re.VERBOSE)



def split_text_into_tokens(text):
    tokens = []
    for match in PATTERN.finditer(text):
        if match.group("newline"):
            tokens.append({"type": "NEW_LINE", "text": "\n"})
        elif match.group("formula"):
            tokens.append({"type": "FORMULA", "text": match.group("formula")})
        elif match.group("word"):
            tokens.append({"type": "WORD", "text": match.group("word")})
    return tokens

def get_text_width(text, font):
    return font.getlength(text)
    
def apply_text_style(elem, font_size, font_family="Arial    "):
    elem.set("style", f"font-size:{font_size}px; font-family:{font_family};")
    
def set_slot_font_size(slot, font_size):
    existing_style = slot.get("style", "").strip()
    if existing_style and not existing_style.endswith(";"):
        existing_style += ";"
    new_style = f"{existing_style}font-size:{font_size}px;"
    slot.set("style", new_style)


def get_svg_width(svg_fragment):
    try:
        root = etree.fromstring(svg_fragment.encode("utf-8"))
        view_box = root.get("viewBox")
        if view_box:
            _, _, width, _ = [float(v) for v in view_box.split()]
            return width
    except Exception:
        pass
    return 0.0

def render_text_in_slot(root, slot_id, text):
    slot = root.xpath(f'//*[@id="{slot_id}"]')[0]
    set_slot_font_size (slot, FONT_SIZE)
    slot_width = float(slot.get("width"))

    font = ImageFont.truetype(FONT_PATH, size=FONT_SIZE)
    LINE_HEIGHT_px = FONT_SIZE * LINE_HEIGHT
    
    x_start = float(slot.get("x")) + 10
    y_start = float(slot.get("y")) + 40
    cursor_x = x_start
    cursor_y = y_start

    tokens = split_text_into_tokens(text)
    for token in tokens:
        if token["type"] in ("WORD", "SPACE"):
            width = get_text_width(token["text"], font)
            if cursor_x + width > x_start + slot_width:
                cursor_y += LINE_HEIGHT_px
                cursor_x = x_start
            text_elem = etree.Element("text", x=str(cursor_x), y=str(cursor_y))
            text_elem.text = token["text"]
            apply_text_style(text_elem, FONT_SIZE)
            root.append(text_elem)  
            #text_elem = etree.Element("text", x=str(cursor_x), y=str(cursor_y)) # , FONT_SIZE=str(FONT_SIZE))
            #text_elem.text = token["text"]
            #root.append(text_elem)
            cursor_x += width

        elif token["type"] == "FORMULA":
            svg = latex_to_svg_fragment(token["text"], scale=LATEX_SCALE)
            if svg:
                width = get_svg_width(svg)
                if cursor_x + width > x_start + slot_width:
                    cursor_y += LINE_HEIGHT_px
                    cursor_x = x_start
                frag_root = etree.fromstring(svg.encode("utf-8"))
                g = etree.Element("g")
                g.extend(list(frag_root))
                offset_y = cursor_y - FONT_SIZE * BASELINE_RATIO
                g.set("transform", f"translate({cursor_x},{offset_y})")
                root.append(g)
                cursor_x += width + 5

        elif token["type"] == "NEW_LINE":
            cursor_y += LINE_HEIGHT_px
            cursor_x = x_start

def main():
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tree = etree.parse("template.svg")
    root = tree.getroot()

    render_text_in_slot(root, "text1_slot", config.get("text1", ""))
    render_text_in_slot(root, "text2_slot", config.get("text2", ""))

    out_path = "out/output.svg"
    os.makedirs("out", exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    print(f"✅ SVG généré : {out_path}")

if __name__ == "__main__":
    main()
