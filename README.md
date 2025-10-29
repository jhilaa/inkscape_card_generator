Modes de syntaxe Latex 
Mode	        En LaTeX	Apparence	                        Usage typique
math	        $ ... $	    compact, dans le flux du texte	    formules courtes intégrées
displaymath	    \[ ... \]	grande, centrée, isolée	            formules mises en valeur
(bonus) text	texte riche avec $...$ à l’intérieur	mixte	texte + formules

math → pour les slots formules
text → pour les slots textes enrichis (avec du LaTeX “littéraire”)
displaymath → pour les formules isolées mises en avant

🧮 1️⃣  Mode math

➡️ Pour les formules pures.
Le moteur LaTeX va entourer ton contenu de $...$ (inline) ou de \[\] (si tu utilises displaymath).

Exemple CSV
formula1_mode;math
formula1;"a^2 + b^2 = c^2"

LaTeX généré par le script
\documentclass[12pt]{standalone}
\usepackage{amsmath,amssymb}
\begin{document}
$a^2 + b^2 = c^2$
\end{document}

🟢 Interprétation :
Tout ce qu’il y a à l’intérieur est lu comme du code mathématique.
Tu ne peux pas y mettre de texte “normal” :
Bonjour sera interprété comme une suite de variables (B, o, n…).
Les espaces sont ignorés, les lettres passent en italique.



🧾 2️⃣  Mode text

➡️ Pour des blocs de texte complet, qui peuvent contenir des formules entre $...$ si besoin.
Exemple CSV
formula1_mode;text
formula1;"\begin{minipage}{10cm}\raggedright
La fameuse équation d’Einstein : $E = mc^2$\\[1em]
Elle relie l’énergie et la masse.
\end{minipage}"

LaTeX généré par le script
\documentclass[12pt]{standalone}
\usepackage{amsmath,amssymb,xcolor}
\begin{document}
\begin{minipage}{10cm}\raggedright
La fameuse équation d’Einstein : $E = mc^2$\\[1em]
Elle relie l’énergie et la masse.
\end{minipage}
\end{document}


🟢 Interprétation :
Le texte est traité comme texte normal :
espaces, accents, ponctuation, etc.
Les maths ne sont reconnues que dans les délimiteurs $...$ ou \[...\].
Tu peux y mettre des environnements (minipage, itemize, couleurs…).


Astuces utiles pour le contenu LaTeX “mixte”
	Gras/italique : \textbf{...}, \emph{...
	Couleurs : \textcolor{#rrggbb}{...} (on a déjà xcolor)
	Taille locale : {\Large ...} ou \fontsize{14}{18}\selectfont
	Listes : itemize, enumerate
	Espacements : \\[0.8em], \vspace{.5em}
	Math inline : $ ... $ ; display : \[ ... \]
	Accents : OK (UTF-8)
	CSV : garde le champ entre guillemets ; un seul antislash pour les commandes LaTeX (\int, \frac, etc.)