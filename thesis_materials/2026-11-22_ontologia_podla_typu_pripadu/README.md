# Pomohla ontológia pri nejakom type prípadu? (2026-11-22)

Porovnanie `onto_project` s `qwen_base` po podskupinách. Zdroj čísel:
[hĺbková analýza](../2026-11-22_hlbkova_analyza_evalu/deep_analysis.md), sekcie T3, T4 a R1.

**Záver:** žiadny typ prípadu model s ontológiou nezvládal preukázateľne lepšie.
Rozdiely sú pár prípadov a žiadny nie je štatisticky významný.

## Testing (pass zo 100, podľa focal metódy)

- Najväčšie plus: metódy s `throw`/`throws`, 5 vs 4 z 11 (3 prípady prešli len s
  ontológiou, 2 len bez nej, teda šum).
- Mierne plus: stredná dĺžka metódy (9 vs 7 z 34), 1–2 vetvenia (13 vs 12 z 39).
- Mínus pri zložitom kóde: veľa vetvení (2 vs 3 z 31), dlhé metódy (3 vs 5 z 33),
  metódy s inými typmi projektu (1 vs 3 z 14). Ontológia skôr ťahá model k ťažkým
  vetvám, pre ktoré nemá fixtures.
- Najdlhšie bloky ontológie (99–317 tokenov): 3 vs 4 z 33.

## Refactoring (structural pass, 8–10 prípadov na typ)

- Plus iba Rename Method v MaRV (8 vs 7 z 9).
- Rovnako: Remove Parameter, Rename Class, Rename Parameter, Extract Variable,
  Parameterize Variable.
- Mínus: Rename Variable (6 vs 9 z 9; ontológia pridala 2 neplatné Java výstupy),
  Inline Variable (3 vs 5), Extract Method v MaRV (2 vs 3).
- Pri fine-tuned modeloch neutrálne: `ft_onto` a `ft_v3_onto` 67, `ft_refactoring` 68.

## Interpretácia

Pri podskupine s 10 prípadmi by rozdiel musel byť zhruba 40–50 p.b., aby bol
preukázateľný; pri 100 prípadoch je MDE okolo ±10 p.b. Do práce ako hypotéza, nie
zistenie: ontológia skôr škodí pri zložitejšom kóde a pri jednoduchých premenovaniach.
