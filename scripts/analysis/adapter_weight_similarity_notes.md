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
