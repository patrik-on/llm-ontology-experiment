# Prečo ontológia nepriniesla zlepšenie (2026-11-21)

Predbežná interpretácia po testing behu, napísaná pred dokončením refactoringu a pred
[hĺbkovou analýzou](../2026-11-22_hlbkova_analyza_evalu/deep_analysis.md), ktorá ju
neskôr overila na číslach. Ide o hypotézy do diskusie, nie o samostatné meranie.

## Hypotézy

1. **Ontológia nepridáva novú informáciu.** Graf sa stavia iba z dodaného kódu (aby
   neunikla gold odpoveď) a ten istý kód model vidí celý v prompte. Medián bloku je
   79 tokenov. `onto_project` vs `qwen_base`: presne +0. Aj eval_loss pri tréningu je
   takmer rovnaký (0,5402 bez blokov, 0,5407 s blokmi).
2. **Efekt nie je nulový, ale náhodný v smere.** `qwen_base` aj `onto_project` majú
   po 22 passoch, zhodujú sa však iba v 16 triedach: blok zmenil výsledok v 12
   prípadoch, 6-krát k lepšiemu a 6-krát k horšiemu. To vyzerá na citlivosť na
   prompt, nie systematický prínos.
3. **Ontológia mierne škodí kompilácii** (`onto_project` 67 vs `qwen_base` 71,
   `ft_onto` 69 vs `ft_v3_onto` 72). Riadok s kandidátmi hraničných hodnôt ťahá model
   k agresívnym vstupom (napr. nemožné `length() = -1`) a potom zle odhadne assert.
4. **FT pomohol, lebo mení správanie, nie znalosti:** model sa naučil tvar testov
   Methods2Test. Pozor, `ft_testing` (53) vs `qwen_base` (22) nie je čisté porovnanie:
   FT ramená bežia cez HF (NF4), ostatné cez Ollamu (Q4), takže +31 p.b. je opisný údaj.
5. **`ft_v3_onto` (48) < `ft_testing` (53):** adaptér v3 bloky pri tréningu nevidel,
   je to preň vstup mimo distribúcie. `ft_onto` (51) na nich trénovaný bol a
   `ft_testing` dorovná, ale neprekoná.
6. **Skill pomáha s formou, nie s logikou:** kompilácia 78 vs 71, class pass rovnaký.
   Opisuje iteratívny postup, protokol je však jednokrokový bez nástrojov.
7. **Malá štatistická sila:** pri 10–25 nesúhlasných pároch McNemar s Holmovou
   korekciou odhalí až rozdiel nad ~10 p.b.

## Formulácia do práce

„Bez preukázateľného efektu pri N = 100“, s nesúhlasnými pármi a minimálnym
detekovateľným efektom. Do diskusie: ontológia zostavená z viditeľného kódu je pre
model nadbytočná; potenciál má informácia mimo kontextu, napríklad vzťahy medzi
triedami a invarianty projektu.
