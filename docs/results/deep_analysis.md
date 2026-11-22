# Hĺbková analýza evalu (2026-11-22)

Zdroj: len uložené výsledky (`testing-matrix-20261122-rag2`, `refactoring-matrix-20261121`), žiadne volania modelu ani GPU. Tokeny: Qwen2.5-Coder-7B-Instruct tokenizer (CPU). Prípady sú zvolené zo zdrojov s fixnými kvótami (convenience), často zoskupené podľa projektu – všetky p-hodnoty sú podmienené týmito prípadmi.

## Hlavné zistenia

1. **Ontológia (onto_project, skills_onto) nič merateľné nepridáva.** V testingu je to 6/6 nesúhlasných párov, v refactoringu 5/10. Pri n=100 a 9–17 % nesúhlasných párov je minimálny odhaliteľný efekt (MDE) ±9 až ±14 p.b. Menší skutočný efekt by tento dizajn nezachytil, takže nulový výsledok je „nedokázané“, nie „neexistuje“.
2. **Fine-tuning je jediný veľký efekt, ale porovnanie ide cez iný backend (len deskriptívne).** V testingu má ft_testing o +31 p.b. viac ako qwen_base (bootstrap CI +18 až +44). Odstraňuje hlavne nebalansované/neparsovateľné telá (u Ollama ramien 8–21 buniek, u FT 0) a assertion failures (47 → 18). Nové chyby pridáva pri kompilácii, napríklad `Lists` (pravdepodobne Guava), ktorú nemá na classpath, alebo chýbajúce importy. Tie však zachytávajú menej buniek, než FT ušetrí. Výhoda FT rastie so zložitosťou metódy: pri 3+ vetvách je 18/31 vs 3/31.
3. **rag_single škodí.**
   - Testing: −8 p.b. (6/14), deskriptívne. Retrieval nikdy nepriniesol nič z rovnakého projektu ani triedy, čo zodpovedá splitu na úrovni projektu, takže leakage je 0/100. Model z kontextu prevzal symboly, ktoré v projekte neexistujú: 4 projektové (napr. `ByteBufferUtil`) a `Arrays` bez importu.
   - Refactoring: −23 p.b. (4/27). Prompt sa natiahne na mediánových 8,9k tokenov (base ~1k). Len 17 % príkladov má rovnaký typ refaktoringu a 41 je „unknown“. Ani keď príklad správneho typu prítomný je, výsledok je 15/29 vs 23/29 pre base. 10 no_op buniek je takmer doslovná ozvena vstupu: zmenené sú iba prázdne riadky alebo licenčná hlavička, žiadna operácia.
4. **FT ramená na SWE (0/5) nie sú obeťou orezania.** Finish je `eos`, `output_truncated=False` a vstup má 0,6–1,4k tokenov pri limite 8192. FT model súbor väčšinou len zopakuje, iba s preformátovaním: medzi importy a polia vloží prázdne riadky, rovnako ako v trénovacích dátach (ML4Ref). Na 12dbeafe všetky 3 FT ramená zmenili `java.io.UncheckedIOException` na staré `org.apache.commons.io.UncheckedIOException`, čo vyzerá ako zapamätaná staršia verzia commons-io (hypotéza). Pri n=5 ide len o anekdotu.
5. **Najčastejšou príčinou neúspechu v refactoringu je, že RefactoringMiner nenašiel požadovanú operáciu na cieli.** Pri Ollama ramenách často deteguje „Change Class Access Modifier“: model prepíše `public class` na package-private, alebo vráti kontextovú jednotku bez modifikátora. Pri Parameterize Variable sa to stalo 28×. FT ramená miesto toho robia „Add Parameter“ a „Remove Parameter“.
6. **Čo sa nedalo zistiť z uložených súborov:** timeouty (nevyskytli sa žiadne) a symbol „vymyslený z ontológie“ (0 výskytov). Ontológia sa skôr prejavuje tým, že tlačí model k ťažkým vetvám, pre ktoré nemá fixtures (napr. `instanceof Enum` → vymyslené `MyEnum`). Počet „iných projektových typov“ v T3 je heuristika založená na regexoch.

## TESTING

### T1. Taxonómia zlyhaní na rameno (prvá chyba kompilácie určuje kategóriu)

| Rameno | pass | compile:access_violation | compile:CFS:class | compile:CFS:method | compile:CFS:variable | compile:incompatible_types | compile:syntax | compile:wrong_arguments | NA:empty_or_escape | NA:forbidden_construct | NA:invalid_json | NA:unbalanced_body | runtime:assertion_failure | runtime:unexpected_exception | method line credit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen_base | 22 | 1 | 0 | 0 | 0 | 1 | 6 | 1 | 1 | 0 | 1 | 18 | 47 | 2 | 0.211 |
| onto_project | 22 | 0 | 2 | 0 | 0 | 2 | 7 | 0 | 1 | 0 | 0 | 21 | 43 | 2 | 0.214 |
| skills | 21 | 1 | 0 | 1 | 0 | 2 | 5 | 1 | 2 | 1 | 1 | 8 | 54 | 3 | 0.205 |
| skills_onto | 23 | 0 | 2 | 0 | 0 | 2 | 8 | 0 | 1 | 0 | 0 | 12 | 49 | 3 | 0.224 |
| rag_single | 14 | 0 | 3 | 1 | 8 | 1 | 4 | 2 | 2 | 0 | 0 | 19 | 45 | 1 | 0.137 |
| ft_testing | 53 | 1 | 3 | 0 | 6 | 1 | 1 | 8 | 2 | 1 | 5 | 0 | 18 | 1 | 0.444 |
| ft_v3_onto | 48 | 1 | 3 | 3 | 6 | 0 | 2 | 7 | 2 | 0 | 4 | 0 | 23 | 1 | 0.388 |
| ft_onto | 51 | 1 | 3 | 2 | 8 | 1 | 2 | 7 | 2 | 0 | 5 | 0 | 18 | 0 | 0.430 |

Timeout: v uložených výsledkoch sa nevyskytol ani jeden (statusy sú len passed / assertion_failure / execution_error / compile_failure). `runtime:unexpected_exception` = test spadol na inej výnimke než AssertionFailedError (napr. UnsupportedOperationException, NPE). Method line credit = pokrytie riadkov focal metódy, ak trieda prešla, inak 0.

Všetky javac chyby (nie len prvá) v bunkách, ktoré nekompilovali:

| Rameno | buniek s compile fail | access_violation | CFS:class | CFS:method | CFS:variable | incompatible_types | other_compile | syntax | wrong_arguments |
|---|---|---|---|---|---|---|---|---|---|
| qwen_base | 9 | 1 | 0 | 0 | 0 | 1 | 0 | 13 | 1 |
| onto_project | 11 | 0 | 4 | 0 | 0 | 3 | 0 | 25 | 0 |
| skills | 10 | 1 | 0 | 2 | 2 | 4 | 0 | 17 | 1 |
| skills_onto | 12 | 0 | 4 | 0 | 0 | 3 | 1 | 21 | 0 |
| rag_single | 19 | 0 | 6 | 3 | 13 | 1 | 3 | 8 | 4 |
| ft_testing | 20 | 1 | 5 | 0 | 33 | 1 | 0 | 1 | 10 |
| ft_v3_onto | 22 | 1 | 8 | 6 | 35 | 0 | 0 | 26 | 7 |
| ft_onto | 24 | 1 | 10 | 4 | 36 | 2 | 0 | 2 | 8 |

Najčastejšie chýbajúce symboly (cannot find symbol, unikátne na bunku):

| Rameno | symboly |
|---|---|
| qwen_base |  |
| onto_project | MyEnum×1, ByteArrayInputStream×1 |
| skills | Arrays×1, seekBufferToNextMultipleOfEight×1 |
| skills_onto | MyEnum×1, ByteArrayInputStream×1 |
| rag_single | Arrays×6, seekBufferToNextMultipleOfEight×1, ByteArrayInputStream×1, ArrayList×1, ByteBufferUtil×1, getEmptyImplementationForCollectionInterface×1 |
| ft_testing | Lists×5, ArrayList×3, HALF_PI×1 |
| ft_v3_onto | Lists×5, assertThat×3, ArrayList×2, ByteArrayInputStream×1, Arrays×1 |
| ft_onto | Lists×6, ArrayList×2, Enum1×1, ByteArrayInputStream×1, DataInputStream×1, bytesToInts×1 |

### T2. Nesúhlasné prípady a ako sa preklopili (kategória B → kategória A)

**onto_project vs qwen_base** – A prešlo, B nie (6): B zlyhalo ako runtime:assertion_failure 3×, not_assembled:unbalanced_body 1×, compile:syntax 1×, not_assembled:invalid_json 1×. 
B prešlo, A nie (6): A zlyhalo ako runtime:assertion_failure 4×, compile:cannot_find_symbol:class 2×.
Prípady A-only: 125332958_120, 159218865_100, 46648544_120, 74562982_99, 99995945_138, 133340671_109; B-only: 5973732_200, 179549243_826, 13357953_0, 29480568_2527, 30952948_965, 30952948_1058

**ft_v3_onto vs ft_testing** – A prešlo, B nie (5): B zlyhalo ako not_assembled:invalid_json 2×, runtime:unexpected_exception 1×, compile:incompatible_types 1×, compile:cannot_find_symbol:class 1×. 
B prešlo, A nie (10): A zlyhalo ako runtime:assertion_failure 4×, compile:cannot_find_symbol:method 3×, runtime:unexpected_exception 1×, not_assembled:invalid_json 1×, compile:cannot_find_symbol:variable 1×.
Prípady A-only: 6101685_163, 37871055_58, 80633575_0, 30952948_1176, 30952948_965; B-only: 241153419_13, 46648544_107, 858685_213, 858685_182, 177212349_345, 177212349_369, 177212349_374, 30952948_139, 12537665_103, 31415856_53

**ft_onto vs ft_v3_onto** – A prešlo, B nie (7): B zlyhalo ako runtime:assertion_failure 3×, compile:cannot_find_symbol:method 2×, runtime:unexpected_exception 1×, compile:cannot_find_symbol:variable 1×. 
B prešlo, A nie (4): A zlyhalo ako not_assembled:invalid_json 2×, compile:cannot_find_symbol:variable 1×, compile:syntax 1×.
Prípady A-only: 241153419_13, 858685_182, 261751286_16, 177212349_345, 177212349_374, 30952948_139, 12537665_103; B-only: 5973732_200, 159218865_100, 30952948_1176, 30952948_965

**skills_onto vs skills** – A prešlo, B nie (8): B zlyhalo ako runtime:assertion_failure 5×, compile:cannot_find_symbol:method 1×, not_assembled:unbalanced_body 1×, runtime:unexpected_exception 1×. 
B prešlo, A nie (6): A zlyhalo ako runtime:assertion_failure 5×, not_assembled:unbalanced_body 1×.
Prípady A-only: 11673895_20, 159218865_73, 159218865_100, 37871055_55, 46648544_120, 177212349_345, 78477907_2, 99995945_138; B-only: 13357953_0, 261751286_17, 29480568_2527, 3694329_20, 30952948_965, 30952948_928

**skills_onto vs onto_project** – A prešlo, B nie (5): B zlyhalo ako not_assembled:unbalanced_body 3×, runtime:assertion_failure 2×. 
B prešlo, A nie (4): A zlyhalo ako runtime:assertion_failure 3×, not_assembled:unbalanced_body 1×.
Prípady A-only: 11673895_20, 77034155_1, 37871055_55, 206366_92, 12537665_103; B-only: 125332958_120, 261751286_17, 30952948_928, 74562982_99

**rag_single vs qwen_base** – A prešlo, B nie (6): B zlyhalo ako runtime:assertion_failure 5×, not_assembled:unbalanced_body 1×. 
B prešlo, A nie (14): A zlyhalo ako compile:cannot_find_symbol:variable 5×, runtime:assertion_failure 4×, not_assembled:unbalanced_body 3×, compile:cannot_find_symbol:method 1×, compile:cannot_find_symbol:class 1×.
Prípady A-only: 50872805_15, 858685_214, 30952948_1176, 11830269_91, 91349782_7, 99995945_138; B-only: 5973732_200, 3487509_20, 159218865_73, 179549243_826, 46648544_37, 46648544_77, 13357953_0, 177212349_369, 177212349_374, 29480568_950, 30952948_965, 30952948_928, 30952948_1058, 78477907_2

### T3. Podskupiny podľa focal metódy (pass rate na rameno; Δ = rozdiel v p.b. s počtom A-only/B-only)

Heuristiky zo zdroja v `case.json` (`input_text`): vetvenie = if/for/while/case/catch/do/ternárny `?`; iné projektové typy = identifikátory s veľkým začiatočným písmenom v tele metódy mimo bežných JDK typov a mimo samotnej triedy (aproximácia). 

**vetvenie**

| úroveň | n | qwen_base | onto_project | skills | skills_onto | rag_single | ft_testing | ft_v3_onto | ft_onto | Δ onto−base | Δ rag−base |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 30 | 7 | 7 | 9 | 7 | 8 | 14 | 13 | 15 | +0 (1/1) | +3 (2/1) |
| 1–2 | 39 | 12 | 13 | 10 | 13 | 6 | 21 | 18 | 18 | +3 (3/2) | -15 (4/10) |
| 3+ | 31 | 3 | 2 | 2 | 3 | 0 | 18 | 17 | 18 | -3 (2/3) | -10 (0/3) |

**throws/throw**

| úroveň | n | qwen_base | onto_project | skills | skills_onto | rag_single | ft_testing | ft_v3_onto | ft_onto | Δ onto−base | Δ rag−base |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nie | 89 | 18 | 17 | 18 | 17 | 14 | 45 | 40 | 44 | -1 (3/4) | -4 (6/10) |
| áno | 11 | 4 | 5 | 3 | 6 | 0 | 8 | 8 | 7 | +9 (3/2) | -36 (0/4) |

**LOC metódy (tercily ≤5, ≤12)**

| úroveň | n | qwen_base | onto_project | skills | skills_onto | rag_single | ft_testing | ft_v3_onto | ft_onto | Δ onto−base | Δ rag−base |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 (nízke) | 33 | 10 | 10 | 10 | 9 | 9 | 17 | 14 | 17 | +0 (1/1) | -3 (2/3) |
| T2 | 34 | 7 | 9 | 7 | 10 | 5 | 18 | 16 | 16 | +6 (3/1) | -6 (4/6) |
| T3 (vysoké) | 33 | 5 | 3 | 4 | 4 | 0 | 18 | 18 | 18 | -6 (2/4) | -15 (0/5) |

**iné projektové typy v metóde**

| úroveň | n | qwen_base | onto_project | skills | skills_onto | rag_single | ft_testing | ft_v3_onto | ft_onto | Δ onto−base | Δ rag−base |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 86 | 19 | 21 | 20 | 19 | 14 | 46 | 41 | 43 | +2 (6/4) | -6 (6/11) |
| 1–2 | 14 | 3 | 1 | 1 | 4 | 0 | 7 | 7 | 8 | -14 (0/2) | -21 (0/3) |

**LOC triedy (tercily ≤9, ≤17)**

| úroveň | n | qwen_base | onto_project | skills | skills_onto | rag_single | ft_testing | ft_v3_onto | ft_onto | Δ onto−base | Δ rag−base |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 (nízke) | 35 | 10 | 10 | 10 | 8 | 11 | 18 | 17 | 19 | +0 (1/1) | +3 (3/2) |
| T2 | 35 | 8 | 9 | 8 | 11 | 3 | 19 | 15 | 15 | +3 (3/2) | -14 (3/8) |
| T3 (vysoké) | 30 | 4 | 3 | 3 | 4 | 0 | 16 | 16 | 17 | -3 (2/3) | -13 (0/4) |

### T4. Ontológia

Dĺžka bloku v tokenoch: medián 79, rozsah 39–317. Pass podľa tercilu dĺžky bloku:

| tercil | n | tokeny | qwen_base | onto_project | skills | skills_onto | ft_v3_onto | ft_onto |
|---|---|---|---|---|---|---|---|---|
| T1 (nízke) | 33 | 39–62 | 8 | 9 | 10 | 8 | 13 | 16 |
| T2 | 34 | 64–97 | 10 | 10 | 8 | 10 | 17 | 20 |
| T3 (vysoké) | 33 | 99–317 | 4 | 3 | 3 | 5 | 18 | 15 |

Prítomnosť riadku „Boundary candidates“ v bloku:

| boundary | n | qwen_base | onto_project | skills | skills_onto | ft_v3_onto | ft_onto |
|---|---|---|---|---|---|---|---|
| áno | 29 | 5 | 4 | 4 | 5 | 17 | 15 |
| nie | 71 | 17 | 18 | 17 | 18 | 31 | 36 |

„Cannot find symbol“, ktorého symbol je v ontologickom bloku, ale NIE v zdrojovom kóde (vymyslené z bloku). Pre ne-onto ramená je to kontrolný výskyt (rovnaký blok prípadu, ktorý model nevidel):

| Rameno | vidí blok | buniek | symbolov |
|---|---|---|---|
| qwen_base | nie | 0 | 0 |
| onto_project | áno | 0 | 0 |
| skills | nie | 0 | 0 |
| skills_onto | áno | 0 | 0 |
| rag_single | nie | 0 | 0 |
| ft_testing | nie | 0 | 0 |
| ft_v3_onto | áno | 0 | 0 |
| ft_onto | áno | 0 | 0 |

### T5. RAG (rag_single, testing)

| Metrika | Hodnota |
|---|---|
| počet kontextov na prípad | 1: 1×, 2: 8×, 3: 91× |
| similarity score (bge-m3) medián / min / max | 0.706 / 0.560 / 0.750 |
| prípady s ≥1 kontextom z rovnakého projektu | 0/100 |
| prípady s ≥1 kontextom o rovnakej triede (meno triedy v produkčnom kóde) | 0/100 |
| LEAKAGE: retrieved test volá rovnakú triedu aj focal metódu | 0/100 |
| prompt tokeny medián qwen_base → rag_single | 1264 → 2738 (+1474) |
| retrieval tokeny medián | 1235 |
| CFS symbol je v retrieved kontexte, nie v zdroji – rag_single (všetky / len projektové, nie JDK) | 7 buniek / 7 symbolov; projektové: 4 buniek (206366_94: ByteBufferUtil; 177212349_369: getEmptyImplementationForCollectionInterface; 29480568_231: CreateSnapshotRequestBinder; 30952948_970: InvalidDataException) |
| to isté pre qwen_base (kontrola, kontext nevidel) | 0 buniek / 0 symbolov; projektové: 0 |

Pass podľa toho, či retrieval priniesol kontext z rovnakého projektu:

| rovnaký projekt | n | qwen_base | rag_single |
|---|---|---|---|
| áno | 0 | 0 | 0 |
| nie | 100 | 22 | 14 |

### T6. Dĺžka promptu (input tokeny) vs. pass

| Rameno | medián tokenov | pass T1 | pass T2 | pass T3 | medián pass | medián fail | Mann-Whitney p |
|---|---|---|---|---|---|---|---|
| qwen_base | 1264 | 8/33 | 9/34 | 5/33 | 1256 | 1269 | 0.229 |
| onto_project | 1367 | 7/33 | 12/34 | 3/33 | 1350 | 1388 | 0.085 |
| skills | 3274 | 11/35 | 6/33 | 4/32 | 3254 | 3290 | 0.057 |
| skills_onto | 3375 | 6/33 | 12/34 | 5/33 | 3367 | 3385 | 0.715 |
| rag_single | 2738 | 6/33 | 6/34 | 2/33 | 2577 | 2750 | 0.150 |
| ft_testing | 985 | 19/35 | 16/33 | 18/32 | 980 | 995 | 0.619 |
| ft_v3_onto | 1086 | 17/33 | 11/34 | 20/33 | 1100 | 1075 | 0.888 |
| ft_onto | 1086 | 19/33 | 14/34 | 18/33 | 1079 | 1104 | 0.426 |

Pozn.: dĺžka promptu silne koreluje s veľkosťou triedy, takže ide o asociáciu, nie o kauzálny vplyv dĺžky.

### Testing (class pass): Wilson 95 % CI na rameno

| Rameno | Úspech | Wilson 95 % |
|---|---|---|
| qwen_base | 22/100 | 15.0–31.1 % |
| onto_project | 22/100 | 15.0–31.1 % |
| skills | 21/100 | 14.2–30.0 % |
| skills_onto | 23/100 | 15.8–32.2 % |
| rag_single | 14/100 | 8.5–22.1 % |
| ft_testing | 53/100 | 43.3–62.5 % |
| ft_v3_onto | 48/100 | 38.5–57.7 % |
| ft_onto | 51/100 | 41.3–60.6 % |

### Testing (class pass): primárne páry – paired bootstrap (10 000, seed 42) a MDE (80 % sila, exaktný McNemar)

MDE = najmenší skutočný rozdiel v p.b., ktorý by test pri pozorovanej miere nesúhlasných párov a n=100 odhalil s 80 % silou; α=0,05 nekorigované, α=0,01 ≈ Holm pre najmenšie p z 5 párov.

| A vs B | A only / B only | Δ (p.b.) | bootstrap 95 % CI | p | p Holm | nesúhlasné | MDE α=0,05 | MDE α=0,01 |
|---|---|---|---|---|---|---|---|---|
| onto_project vs qwen_base | 6/6 | +0.0 | -7.0 až +7.0 | 1.0000 | 1.0000 | 12 % | ±10 | ±12 |
| ft_v3_onto vs ft_testing | 5/10 | -5.0 | -12.0 až +2.0 | 0.3018 | 1.0000 | 15 % | ±11 | ±13 |
| ft_onto vs ft_v3_onto | 7/4 | +3.0 | -3.0 až +9.0 | 0.5488 | 1.0000 | 11 % | ±10 | ±11 |
| skills_onto vs skills | 8/6 | +2.0 | -5.0 až +9.0 | 0.7905 | 1.0000 | 14 % | ±11 | ±13 |
| skills_onto vs onto_project | 5/4 | +1.0 | -5.0 až +7.0 | 1.0000 | 1.0000 | 9 % | ±9 | nedosiahnuteľné |

### Testing (class pass): doplnkové porovnania (DESKRIPTÍVNE – iný backend alebo mimo predeklarovaných párov, bez Holma)

| A vs B | A only / B only | Δ (p.b.) | bootstrap 95 % CI | p (nekorigované) |
|---|---|---|---|---|
| rag_single vs qwen_base | 6/14 | -8.0 | -17.0 až +1.0 | 0.12 |
| ft_testing vs qwen_base | 42/11 | +31.0 | +18.0 až +44.0 | 2.2e-05 |
| ft_v3_onto vs onto_project | 39/13 | +26.0 | +13.0 až +39.0 | 0.00041 |
| ft_onto vs onto_project | 41/12 | +29.0 | +16.0 až +42.0 | 8.2e-05 |
| ft_onto vs qwen_base | 42/13 | +29.0 | +15.0 až +43.0 | 0.00011 |

## REFACTORING

### R1. Status na rameno × zdroj × typ refaktoringu

Skratky: SP = structural_pass, P = passed (SWE overené), CF = checks_failed, IJ = invalid_java, NO = no_op, MOF = model_output_failure.

| zdroj | operácia | n | qwen_base | onto_project | skills | skills_onto | rag_single | ft_refactoring | ft_v3_onto | ft_onto |
|---|---|---|---|---|---|---|---|---|---|---|
| marv | Extract Method | 9 | SP3 CF4 IJ2 | SP2 CF5 IJ2 | SP1 CF7 IJ1 | SP2 CF6 IJ1 | CF7 IJ1 NO1 | SP4 CF4 MOF1 | SP5 CF3 MOF1 | SP5 CF2 MOF2 |
| marv | Remove Parameter | 8 | SP5 IJ1 MOF2 | SP5 IJ1 MOF2 | SP3 CF1 IJ2 MOF2 | SP5 IJ1 MOF2 | SP3 CF2 IJ1 NO1 MOF1 | SP4 CF1 NO1 MOF2 | SP4 CF2 NO1 MOF1 | SP4 NO2 MOF2 |
| marv | Rename Method | 9 | SP7 CF1 IJ1 | SP8 IJ1 | SP6 IJ3 | SP6 IJ3 | SP6 CF1 NO1 MOF1 | SP8 MOF1 | SP6 CF1 NO1 MOF1 | SP7 CF1 MOF1 |
| marv | Rename Variable | 9 | SP9 | SP6 CF1 IJ2 | SP6 IJ3 | SP8 IJ1 | SP6 CF1 IJ2 | SP9 | SP9 | SP9 |
| ml4refactoring | Extract Variable | 10 | SP4 CF4 IJ2 | SP4 CF4 IJ2 | SP2 CF7 IJ1 | SP3 CF6 IJ1 | SP1 CF7 IJ2 | SP7 CF3 | SP7 CF3 | SP6 CF4 |
| ml4refactoring | Inline Variable | 10 | SP5 CF3 IJ2 | SP3 CF4 IJ2 NO1 | SP2 CF5 IJ2 NO1 | SP4 CF3 IJ2 NO1 | SP2 CF5 IJ2 NO1 | SP7 CF2 IJ1 | SP5 CF2 IJ1 NO1 MOF1 | SP7 CF2 IJ1 |
| ml4refactoring | Parameterize Variable | 10 | SP1 CF6 IJ2 NO1 | SP1 CF9 | SP2 CF7 IJ1 | CF9 NO1 | CF6 IJ1 NO1 MOF2 | SP5 CF5 | SP7 CF3 | SP6 CF4 |
| ml4refactoring | Rename Class | 10 | SP9 IJ1 | SP9 IJ1 | SP10 | SP10 | SP10 | SP9 MOF1 | SP9 MOF1 | SP9 MOF1 |
| ml4refactoring | Rename Parameter | 10 | SP9 IJ1 | SP9 IJ1 | SP9 IJ1 | SP9 IJ1 | SP7 CF2 IJ1 | SP10 | SP10 | SP10 |
| ml4refactoring | Replace Variable With Attribute | 10 | SP5 CF4 IJ1 | SP4 CF4 IJ2 | SP4 CF4 IJ2 | SP3 CF5 IJ2 | SP2 CF6 IJ2 | SP5 CF4 IJ1 | SP5 CF4 IJ1 | SP4 CF5 IJ1 |
| swe | Extract Method | 4 | P1 CF3 | P1 CF3 | P1 CF3 | P1 CF3 | NO4 | CF1 NO3 | CF1 NO3 | CF2 NO2 |
| swe | Inline Method | 1 | CF1 | CF1 | CF1 | CF1 | NO1 | NO1 | NO1 | NO1 |

Súčty:

| Rameno | SP | P | CF | IJ | NO | MOF |
|---|---|---|---|---|---|---|
| qwen_base | 57 | 1 | 26 | 13 | 1 | 2 |
| onto_project | 51 | 1 | 31 | 14 | 1 | 2 |
| skills | 45 | 1 | 35 | 16 | 1 | 2 |
| skills_onto | 50 | 1 | 33 | 12 | 2 | 2 |
| rag_single | 37 | 0 | 37 | 12 | 10 | 4 |
| ft_refactoring | 68 | 0 | 20 | 2 | 5 | 5 |
| ft_v3_onto | 67 | 0 | 19 | 2 | 7 | 5 |
| ft_onto | 67 | 0 | 20 | 2 | 5 | 6 |

### R2. checks_failed – čo konkrétne zlyhalo

Kategórie: *op_missing+iné* = RefactoringMiner nenašiel požadovanú operáciu na cieli, ale našiel iné refaktoringy; *op_missing+nič* = nenašiel žiadny refaktoring; *op_ok+compile* / *op_ok+test* = operácia sedí, ale SWE build/test zlyhal; *op_missing+compile/test* = SWE bez operácie a zároveň build/test fail.

| Rameno | CF | rozpad | najčastejšie detegované namiesto požadovaného |
|---|---|---|---|
| qwen_base | 26 | op_missing+iné 16, op_missing+nič 6, op_ok+compile 2, op_missing+compile 1, op_missing+build_ok 1 | Change Class Access Modifier×12, Extract Method×5, Rename Variable×4, Remove Variable Modifier×2 |
| onto_project | 31 | op_missing+iné 24, op_ok+compile 3, op_missing+nič 3, op_missing+build_ok 1 | Change Class Access Modifier×19, Extract Method×7, Change Attribute Access Modifier×6, Rename Variable×4 |
| skills | 35 | op_missing+iné 23, op_missing+nič 7, op_ok+compile 3, op_missing+build_ok 1, op_ok+iné 1 | Extract Method×16, Change Class Access Modifier×14, Extract Variable×5, Change Method Access Modifier×3 |
| skills_onto | 33 | op_missing+iné 25, op_ok+compile 3, op_missing+nič 3, op_missing+build_ok 1, op_ok+iné 1 | Change Class Access Modifier×17, Extract Method×10, Remove Parameter×6, Extract Variable×5 |
| rag_single | 37 | op_missing+iné 26, op_missing+nič 10, op_ok+iné 1 | Change Class Access Modifier×15, Remove Parameter×11, Extract Method×5, Replace Variable With Attribute×3 |
| ft_refactoring | 20 | op_missing+iné 11, op_missing+nič 8, op_missing+compile 1 | Add Parameter×12, Inline Variable×3, Extract Method×2, Remove Variable Modifier×2 |
| ft_v3_onto | 19 | op_missing+iné 12, op_missing+nič 6, op_missing+compile 1 | Add Parameter×12, Inline Variable×3, Rename Variable×2, Extract Variable×2 |
| ft_onto | 20 | op_missing+iné 10, op_missing+nič 8, op_missing+compile 2 | Remove Parameter×8, Change Variable Type×7, Inline Variable×4, Replace Variable With Attribute×4 |

Pre neúspešné bunky (op_missing, MaRV/ML4Ref): požadovaná operácia → čo RefactoringMiner reálne detegoval (všetky ramená spolu):

| požadovaná | bez detekcie | detegované namiesto |
|---|---|---|
| Extract Method | 15 | Extract Method×17, Change Class Access Modifier×8, Remove Class Modifier×3, Add Parameter×3 |
| Extract Variable | 16 | Extract Variable×18, Change Class Access Modifier×4, Encapsulate Attribute×3, Extract Method×2 |
| Inline Variable | 10 | Change Class Access Modifier×16, Inline Variable×2, Remove Parameter×1 |
| Parameterize Variable | 4 | Change Class Access Modifier×28, Rename Variable×21, Remove Variable Modifier×6, Add Parameter×4 |
| Remove Parameter | 0 | Change Parameter Type×4, Rename Parameter×4, Change Class Access Modifier×1, Remove Parameter×1 |
| Rename Method | 1 | Change Method Access Modifier×2, Change Return Type×1 |
| Rename Parameter | 0 | Rename Attribute×1, Move Attribute×1, Move Method×1 |
| Rename Variable | 1 | Change Class Access Modifier×1 |
| Replace Variable With Attribute | 4 | Change Class Access Modifier×18, Change Variable Type×8, Replace Variable With Attribute×8, Change Attribute Type×7 |

### R3. Nesúhlasné prípady (structural success) a preklopenie statusu

**onto_project vs qwen_base** – A-only 5 (B zlyhalo ako checks_failed 4×, invalid_java 1×; operácie swe/Extract Method 1, marv/Rename Method 1, ml4refactoring/Replace Variable With Attribute 1, ml4refactoring/Parameterize Variable 1). B-only 10 (A zlyhalo ako checks_failed 8×, invalid_java 2×; operácie marv/Rename Variable 3, ml4refactoring/Inline Variable 2, ml4refactoring/Replace Variable With Attribute 2, marv/Extract Method 1).

**ft_v3_onto vs ft_refactoring** – A-only 5 (B zlyhalo ako checks_failed 4×, model_output_failure 1×; operácie ml4refactoring/Parameterize Variable 2, marv/Extract Method 1, marv/Remove Parameter 1, ml4refactoring/Extract Variable 1). B-only 6 (A zlyhalo ako no_op 3×, checks_failed 2×, model_output_failure 1×; operácie marv/Rename Method 2, ml4refactoring/Inline Variable 2, marv/Remove Parameter 1, ml4refactoring/Extract Variable 1).

**ft_onto vs ft_v3_onto** – A-only 6 (B zlyhalo ako checks_failed 4×, no_op 1×, model_output_failure 1×; operácie ml4refactoring/Inline Variable 2, marv/Remove Parameter 1, marv/Rename Method 1, marv/Extract Method 1). B-only 6 (A zlyhalo ako checks_failed 4×, model_output_failure 2×; operácie ml4refactoring/Replace Variable With Attribute 2, marv/Extract Method 1, marv/Remove Parameter 1, ml4refactoring/Extract Variable 1).

**skills_onto vs skills** – A-only 11 (B zlyhalo ako checks_failed 8×, invalid_java 3×; operácie ml4refactoring/Inline Variable 3, marv/Remove Parameter 2, marv/Rename Variable 2, ml4refactoring/Extract Variable 2). B-only 6 (A zlyhalo ako checks_failed 5×, invalid_java 1×; operácie ml4refactoring/Parameterize Variable 2, ml4refactoring/Replace Variable With Attribute 2, ml4refactoring/Inline Variable 1, ml4refactoring/Extract Variable 1).

**skills_onto vs onto_project** – A-only 5 (B zlyhalo ako checks_failed 3×, invalid_java 2×; operácie marv/Rename Variable 2, marv/Extract Method 1, ml4refactoring/Inline Variable 1, ml4refactoring/Rename Class 1). B-only 6 (A zlyhalo ako invalid_java 3×, checks_failed 3×; operácie marv/Rename Method 2, marv/Extract Method 1, ml4refactoring/Parameterize Variable 1, ml4refactoring/Replace Variable With Attribute 1).

**rag_single vs qwen_base** – A-only 4 (B zlyhalo ako invalid_java 2×, checks_failed 2×; operácie marv/Remove Parameter 1, ml4refactoring/Replace Variable With Attribute 1, ml4refactoring/Extract Variable 1, ml4refactoring/Rename Class 1). B-only 27 (A zlyhalo ako checks_failed 17×, no_op 6×, invalid_java 3×, model_output_failure 1×; operácie ml4refactoring/Extract Variable 4, ml4refactoring/Replace Variable With Attribute 4, swe/Extract Method 3, marv/Rename Variable 3).

### R4. rag_single v refaktoringu – prečo no_op a slabší výkon

10 no_op buniek rag_single:

| prípad | zdroj | operácia | prompt tok rag | prompt tok base | output tok | kontexty | výstup = vstup? | qwen_base status |
|---|---|---|---|---|---|---|---|---|
| 12dbeafe93f7d63512db1c07cbe7 | swe | Extract Method | 6430 | 631 | 433 | 3 | áno | checks_failed |
| 3ac63df5d5660d14212b9dad50ef | swe | Extract Method | 5747 | 865 | 511 | 3 | nie (0.843) | checks_failed |
| 4d63091bdc21465423ef006c3b1a | swe | Extract Method | 8733 | 1255 | 1088 | 3 | nie (0.993) | passed |
| c28eff3be60085078fcd6bce5613 | swe | Inline Method | 7962 | 1102 | 811 | 3 | nie (0.880) | checks_failed |
| d269f164b3e24a92cc33d759d8bc | swe | Extract Method | 8032 | 1337 | 1094 | 3 | nie (0.913) | checks_failed |
| marv-26dbe5d1e6c7d2b81fc89f2 | marv | Rename Method | 10267 | 1652 | 1285 | 3 | nie (0.928) | invalid_java |
| marv-552dc590d098dd11018a533 | marv | Remove Parameter | 6524 | 746 | 517 | 3 | nie (0.996) | structural_pass |
| marv-83018b0cf6ae0eebc398256 | marv | Extract Method | 8358 | 1139 | 886 | 3 | nie (0.997) | checks_failed |
| ml4refactoring-00b0153739801 | ml4refactoring | Parameterize Variable | 9354 | 1214 | 1046 | 3 | nie (0.986) | structural_pass |
| ml4refactoring-180a7785efdda | ml4refactoring | Inline Variable | 9585 | 1050 | 924 | 3 | nie (0.990) | structural_pass |

| Metrika | Hodnota |
|---|---|
| prompt tokeny medián qwen_base → rag_single | 980 → 8924 |
| prompt tokeny max rag_single | 15796 |
| kontextov na prípad | 3:100× |
| similarity score medián | 0.759 |
| prípady s ≥1 kontextom z rovnakej triedy | 2/100 |
| bunky, kde výstup obsahuje nové riadky doslova z retrieved kontextu (nie zo vstupu) | 4/100, z toho neúspešných 2 |
| retrieved príklady s označeným typom = požadovaná operácia | 50/300 (17 %); 'unknown' 41 |
| prípady s aspoň 1 príkladom požadovaného typu | 29/100 |

| zdroj | n | tok base | tok rag | SS base | SS rag |
|---|---|---|---|---|---|
| marv | 35 | 1105 | 9692 | 24 | 15 |
| ml4refactoring | 60 | 923 | 8679 | 33 | 22 |
| swe | 5 | 1102 | 7962 | 3 | 0 |

### R5. Prečo FT ramená majú 0/5 na SWE

| prípad | rameno | operácia | status | in tok | out tok | finish | truncated | výstup = vstup | zmenených znakov |
|---|---|---|---|---|---|---|---|---|---|
| 12dbeafe93f7 | qwen_base | Extract Method | checks_failed | 631 | 447 | stop | None | nie | 112 |
| 12dbeafe93f7 | ft_refactoring | Extract Method | checks_failed | 602 | 434 | eos | False | nie | 104 |
| 12dbeafe93f7 | ft_v3_onto | Extract Method | checks_failed | 686 | 451 | eos | False | nie | 219 |
| 12dbeafe93f7 | ft_onto | Extract Method | checks_failed | 686 | 433 | eos | False | nie | 88 |
| 3ac63df5d566 | qwen_base | Extract Method | checks_failed | 865 | 712 | stop | None | nie | 260 |
| 3ac63df5d566 | ft_refactoring | Extract Method | no_op | 836 | 694 | eos | False | nie | 7 |
| 3ac63df5d566 | ft_v3_onto | Extract Method | no_op | 1032 | 694 | eos | False | nie | 7 |
| 3ac63df5d566 | ft_onto | Extract Method | no_op | 1032 | 694 | eos | False | nie | 7 |
| 4d63091bdc21 | qwen_base | Extract Method | passed | 1255 | 1121 | stop | None | nie | 187 |
| 4d63091bdc21 | ft_refactoring | Extract Method | no_op | 1226 | 1086 | eos | False | áno | 0 |
| 4d63091bdc21 | ft_v3_onto | Extract Method | no_op | 1310 | 1086 | eos | False | áno | 0 |
| 4d63091bdc21 | ft_onto | Extract Method | no_op | 1310 | 1086 | eos | False | áno | 0 |
| c28eff3be600 | qwen_base | Inline Method | checks_failed | 1102 | 989 | stop | None | nie | 6 |
| c28eff3be600 | ft_refactoring | Inline Method | no_op | 1073 | 989 | eos | False | nie | 3 |
| c28eff3be600 | ft_v3_onto | Inline Method | no_op | 1238 | 989 | eos | False | nie | 3 |
| c28eff3be600 | ft_onto | Inline Method | no_op | 1238 | 989 | eos | False | nie | 3 |
| d269f164b3e2 | qwen_base | Extract Method | checks_failed | 1337 | 1299 | stop | None | nie | 138 |
| d269f164b3e2 | ft_refactoring | Extract Method | no_op | 1308 | 1275 | eos | False | nie | 4 |
| d269f164b3e2 | ft_v3_onto | Extract Method | no_op | 1415 | 1275 | eos | False | nie | 4 |
| d269f164b3e2 | ft_onto | Extract Method | checks_failed | 1415 | 1256 | eos | False | nie | 137 |

no_op podľa zdroja:

| Rameno | no_op | zdroje |
|---|---|---|
| qwen_base | 1 | ml4refactoring 1 |
| onto_project | 1 | ml4refactoring 1 |
| skills | 1 | ml4refactoring 1 |
| skills_onto | 2 | ml4refactoring 2 |
| rag_single | 10 | swe 5, marv 3, ml4refactoring 2 |
| ft_refactoring | 5 | swe 4, marv 1 |
| ft_v3_onto | 7 | swe 4, marv 2, ml4refactoring 1 |
| ft_onto | 5 | swe 3, marv 2 |

### Refactoring (structural success): Wilson 95 % CI na rameno

| Rameno | Úspech | Wilson 95 % |
|---|---|---|
| qwen_base | 60/100 | 50.2–69.1 % |
| onto_project | 55/100 | 45.2–64.4 % |
| skills | 49/100 | 39.4–58.7 % |
| skills_onto | 54/100 | 44.3–63.4 % |
| rag_single | 37/100 | 28.2–46.8 % |
| ft_refactoring | 68/100 | 58.3–76.3 % |
| ft_v3_onto | 67/100 | 57.3–75.4 % |
| ft_onto | 67/100 | 57.3–75.4 % |

### Refactoring (structural success): primárne páry – paired bootstrap (10 000, seed 42) a MDE (80 % sila, exaktný McNemar)

MDE = najmenší skutočný rozdiel v p.b., ktorý by test pri pozorovanej miere nesúhlasných párov a n=100 odhalil s 80 % silou; α=0,05 nekorigované, α=0,01 ≈ Holm pre najmenšie p z 5 párov.

| A vs B | A only / B only | Δ (p.b.) | bootstrap 95 % CI | p | p Holm | nesúhlasné | MDE α=0,05 | MDE α=0,01 |
|---|---|---|---|---|---|---|---|---|
| onto_project vs qwen_base | 5/10 | -5.0 | -13.0 až +2.0 | 0.3018 | 1.0000 | 15 % | ±11 | ±13 |
| ft_v3_onto vs ft_refactoring | 5/6 | -1.0 | -7.0 až +6.0 | 1.0000 | 1.0000 | 11 % | ±10 | ±11 |
| ft_onto vs ft_v3_onto | 6/6 | +0.0 | -7.0 až +7.0 | 1.0000 | 1.0000 | 12 % | ±10 | ±12 |
| skills_onto vs skills | 11/6 | +5.0 | -3.0 až +13.0 | 0.3323 | 1.0000 | 17 % | ±12 | ±14 |
| skills_onto vs onto_project | 5/6 | -1.0 | -7.0 až +5.0 | 1.0000 | 1.0000 | 11 % | ±10 | ±11 |

### Refactoring (structural success): doplnkové porovnania (DESKRIPTÍVNE – iný backend alebo mimo predeklarovaných párov, bez Holma)

| A vs B | A only / B only | Δ (p.b.) | bootstrap 95 % CI | p (nekorigované) |
|---|---|---|---|---|
| rag_single vs qwen_base | 4/27 | -23.0 | -33.0 až -13.0 | 3.4e-05 |
| ft_refactoring vs qwen_base | 21/13 | +8.0 | -3.0 až +19.0 | 0.23 |
| ft_v3_onto vs onto_project | 29/17 | +12.0 | -1.0 až +25.0 | 0.1 |
| ft_onto vs onto_project | 25/13 | +12.0 | +0.0 až +24.0 | 0.073 |
| ft_onto vs qwen_base | 21/14 | +7.0 | -4.0 až +19.0 | 0.31 |


## Adaptéry vo váhovom priestore

Porovnanie štyroch LoRA adaptérov priamo vo váhach (bez modelu a GPU) je v
[adapter_weight_similarity.md](adapter_weight_similarity.md) (čísla v
[JSON](adapter_weight_similarity.json), skript `scripts/analysis/adapter_weight_similarity.py`).
Onto adaptér je blízko svojho ne-onto partnera (kosínus ΔW 0,34 pri testingu, 0,29 pri
refactoringu), kým medzi úlohami je kosínus len 0,015–0,016. Ontológia v tréningových promptoch
teda adaptér posunie oveľa menej než zmena úlohy, no nevznikne takmer rovnaký adaptér.
