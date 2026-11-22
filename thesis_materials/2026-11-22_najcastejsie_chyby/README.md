# Najčastejšie chyby základného modelu a FT (2026-11-22)

Zdroj čísel: [hĺbková analýza](../2026-11-22_hlbkova_analyza_evalu/deep_analysis.md),
sekcie T1, T2 a R2.

**Záver:** pri každom ramene jedna chyba jasne prevláda. Fine-tuning ju zmenšil,
ale nezmenil, ktorá to je.

## Testing (100 prípadov)

Najčastejšia chyba všade: test sa skompiluje a spustí, ale zlyhá assertion (model zle
odhadne očakávanú hodnotu).

| Rameno | assertion fail | ďalšie časté |
|---|---|---|
| `qwen_base` | 47 | nevyvážené telo testu 18, syntax 6 |
| `ft_testing` | 18 | zlé argumenty volania 8, neznáma premenná 6 |
| `ft_v3_onto` | 23 | zlé argumenty 7, neznáma premenná 6 |
| `ft_onto` | 18 | neznáma premenná 8, zlé argumenty 7 |

FT naučil model dodržať tvar výstupu (nevyvážené telo zmizlo) a zlých očakávaných
hodnôt ubudlo zhruba o polovicu. Model však viac odhaduje signatúry.

## Refactoring (100 prípadov)

Najčastejšia chyba: platná Java, ale RefactoringMiner nenájde požadovanú operáciu
(checks_failed).

| Rameno | checks_failed | neplatná Java | no_op | typická náhradná zmena |
|---|---|---|---|---|
| `qwen_base` | 26 | 13 | 1 | Change Class Access Modifier ×12 |
| `ft_refactoring` | 20 | 2 | 5 | Add Parameter ×12 |
| `ft_v3_onto` | 19 | 2 | 7 | Add Parameter ×12 |
| `ft_onto` | 20 | 2 | 5 | Remove Parameter ×8 |

Najťažšia operácia je Parameterize Variable: naprieč ramenami model 28-krát zmenil
modifikátor triedy a 21-krát iba premenoval premennú.
