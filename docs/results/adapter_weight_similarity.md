# Adaptéry vo váhovom priestore

Porovnanie štyroch LoRA adaptérov v3 priamo vo váhach, bez modelu a bez GPU (`scripts/analysis/adapter_weight_similarity.py`). Pre každý cieľový modul je aktualizácia ΔW = s·B·A (s = lora_alpha / r); plné matice sa nevytvárajú, všetko sa počíta cez r×r súčiny.

## Adaptéry

| Adaptér | modulov | škála s | ‖ΔW‖_F spolu | medián ‖ΔW‖_F modulu | sha256 |
|---|---:|---:|---:|---:|---|
| b2_testing | 112 | 2 | 9.211 | 0.687 | `e21f91687e85…` |
| b2_testing_onto | 112 | 2 | 9.260 | 0.687 | `0a4f1af7b145…` |
| b2_refactoring | 112 | 2 | 13.208 | 0.894 | `48ff7f06e8e0…` |
| b2_refactoring_onto | 112 | 2 | 13.418 | 0.992 | `01e55f951a3a…` |

## Konfigurácia

| pole | rovnaké | hodnoty |
|---|---|---|
| `r` | áno | 16 |
| `lora_alpha` | áno | 32 |
| `lora_dropout` | áno | 0.05 |
| `use_rslora` | áno | false |
| `use_dora` | áno | false |
| `bias` | áno | "none" |
| `init_lora_weights` | áno | true |
| `target_modules` | áno | ["k_proj", "o_proj", "q_proj", "v_proj"] |
| `base_model_name_or_path` | áno | "/mnt/c/models/huggingface/Qwen2.5-Coder-7B-Instruct" |
| `peft_version` | áno | "0.21.3" |

## Páry: celkové čísla

*cos ΔW* = kosínus všetkých ΔW spojených do jedného vektora; *medián / IQR* cez moduly; *cos A*, *cos B* = priemerný kosínus samotných matíc; *stĺpce* = Grassmannova podobnosť priestorov span(B) (výstupná strana), *riadky* = span(Aᵀ) (vstupná strana), v zátvorke náhodný baseline r/d; *pomer noriem* = ‖ΔW_A‖ / ‖ΔW_B‖.

| Pár | cos ΔW | medián cos (IQR) | cos A | cos B | stĺpce (baseline) | riadky (baseline) | pomer noriem |
|---|---:|---:|---:|---:|---:|---:|---:|
| b2_testing vs b2_testing_onto | 0.341 | 0.297 (0.177–0.363) | -0.000 | -0.001 | 0.227 (0.0179) | 0.027 (0.0045) | 0.995 |
| b2_testing vs b2_refactoring | 0.015 | 0.009 (0.003–0.017) | -0.000 | -0.000 | 0.047 (0.0179) | 0.007 (0.0045) | 0.697 |
| b2_testing vs b2_refactoring_onto | 0.015 | 0.010 (0.004–0.018) | -0.000 | -0.000 | 0.049 (0.0179) | 0.007 (0.0045) | 0.686 |
| b2_testing_onto vs b2_refactoring | 0.015 | 0.009 (0.003–0.019) | -0.000 | -0.001 | 0.048 (0.0179) | 0.007 (0.0045) | 0.701 |
| b2_testing_onto vs b2_refactoring_onto | 0.016 | 0.010 (0.004–0.020) | 0.002 | 0.001 | 0.050 (0.0179) | 0.007 (0.0045) | 0.690 |
| b2_refactoring vs b2_refactoring_onto | 0.293 | 0.175 (0.086–0.298) | -0.002 | -0.002 | 0.183 (0.0179) | 0.030 (0.0045) | 0.984 |

## Podľa typu projekcie: cos ΔW (stĺpcová podobnosť)

| Pár | k_proj | o_proj | q_proj | v_proj |
|---|---:|---:|---:|---:|
| b2_testing vs b2_testing_onto | 0.176 (0.228) | 0.413 (0.224) | 0.260 (0.182) | 0.355 (0.275) |
| b2_testing vs b2_refactoring | 0.003 (0.087) | 0.022 (0.023) | 0.007 (0.024) | 0.017 (0.054) |
| b2_testing vs b2_refactoring_onto | 0.003 (0.090) | 0.022 (0.023) | 0.007 (0.026) | 0.019 (0.056) |
| b2_testing_onto vs b2_refactoring | 0.002 (0.088) | 0.023 (0.023) | 0.006 (0.024) | 0.019 (0.055) |
| b2_testing_onto vs b2_refactoring_onto | 0.002 (0.089) | 0.023 (0.025) | 0.007 (0.026) | 0.021 (0.058) |
| b2_refactoring vs b2_refactoring_onto | 0.136 (0.176) | 0.355 (0.198) | 0.245 (0.142) | 0.251 (0.218) |

## Podľa hĺbky (tretiny vrstiev): cos ΔW (stĺpcová podobnosť)

| Pár | L0-9 | L10-18 | L19-27 |
|---|---:|---:|---:|
| b2_testing vs b2_testing_onto | 0.326 (0.220) | 0.301 (0.227) | 0.385 (0.236) |
| b2_testing vs b2_refactoring | 0.018 (0.051) | 0.008 (0.041) | 0.018 (0.048) |
| b2_testing vs b2_refactoring_onto | 0.016 (0.054) | 0.009 (0.042) | 0.018 (0.050) |
| b2_testing_onto vs b2_refactoring | 0.017 (0.051) | 0.010 (0.041) | 0.018 (0.050) |
| b2_testing_onto vs b2_refactoring_onto | 0.018 (0.055) | 0.010 (0.043) | 0.019 (0.050) |
| b2_refactoring vs b2_refactoring_onto | 0.112 (0.110) | 0.228 (0.186) | 0.446 (0.262) |

Výpočet trval 2.2 s na CPU.

## Interpretácia

**Onto adaptéry sú blízko svojho ne-onto partnera, ďaleko od druhej úlohy.** Kosínus celej
aktualizácie ΔW je 0,341 pre testing vs testing_onto a 0,293 pre refactoring vs refactoring_onto,
kým medzi úlohami (testing vs refactoring, s ontológiou aj bez nej) je 0,015–0,016, teda asi
20× menej. Rovnaký obraz dáva podobnosť priestorov: stĺpcové priestory span(B) sa v rámci úlohy
zhodujú na 0,23 a 0,18 (náhodný baseline 0,018, teda 10–13× nad náhodou), medzi úlohami len
0,047–0,050 (2,6–2,8× nad náhodou). Pridanie bloku ontológie do tréningových promptov teda
posunie adaptér menej, než ho posunie zmena úlohy.

**Napriek tomu nejde o „takmer rovnaký“ adaptér.** Kosínus 0,3 znamená, že väčšia časť
aktualizácie je pre onto adaptér iná; medián cez moduly je 0,30 (testing) a 0,18 (refactoring).
Pri refactoringu podobnosť rastie s hĺbkou (0,11 → 0,23 → 0,45 po tretinách vrstiev), pri
testingu je rovnomerná (0,30–0,39). Najviac zdieľajú `o_proj` a `v_proj`, najmenej `k_proj`.

**Normy:** adaptér s ontológiou má prakticky rovnakú veľkosť aktualizácie (pomer noriem 0,995 a
0,984); refactoring adaptéry sú o ~45 % „väčšie“ než testing (pomer ~0,69), čo zodpovedá dlhšiemu
tréningu (880 krokov na 3 520 príkladoch vs 500 krokov na 2 300 pri testingu, ktorý zastavil early stopping).

**Inicializácia:** všetky štyri tréningy mali v konfigurácii `seed: 42` a rovnaké LoRA nastavenia
(r=16, alpha=32, dropout 0,05, q/k/v/o), no kosínus samotných matíc A je ≈ 0, teda počiatočné A
neboli rovnaké (generátor náhodných čísel sa pred inicializáciou LoRA zrejme posunul inak). Podobnosť
ΔW preto nevzniká zo spoločného štartu, ale z podobného signálu v dátach. Kosínus A a B osobitne nie
je zmysluplná miera (rozklad B·A je určený len do rotácie v r-rozmernom priestore), preto sa
porovnáva súčin ΔW a jeho podpriestory.

**Vzťah k výsledkom evalu:** blízkosť vo váhach je v súlade s tým, že ft_onto a ft_v3_onto sa
v evaloch nelíšili významne (testing 51 vs 48, refactoring 67 vs 67, Holm p = 1,0). Váhová
podobnosť je však len opis adaptérov, nie dôkaz rovnakého správania.
