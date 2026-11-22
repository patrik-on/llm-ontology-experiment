# V3 fine-tuning runbook (eval-aligned)

## Prečo v3

Adaptéry v2 sa trénovali na úlohe, ktorú matice nehodnotia:

| | Tréning v2 | Evalučné matice (FT ramená) |
|---|---|---|
| Inštrukcia | krátka slovenská veta | anglický kontrakt + scaffold/cieľ + JSON schéma (+ one-shot demo pri testingu) |
| Vstup testing | iba focal metóda (`src_fm`) | obalená produkčná trieda |
| Výstup testing | holá JUnit 4 metóda s `@Test` | JSON `{"testCase1","testCase2"}`, iba telá Jupiter testov |
| Výstup refactoring | holý Java súbor | JSON `{"file_path","refactored_code"}` s kontextovou jednotkou |
| Typy refactoringu | 5 zo 6 ML4Ref typov z kohorty boli `unknown` | 11 typov, presná požadovaná zmena a cieľové riadky |
| Dĺžka | `max_seq_length` 2048, 30 % refactoringu skrátených | kontext 32 768 |

Parsery matíc sú striktné (`json.loads`), takže v2 FT bunky končia ako
`model_output_failure` ešte pred kompiláciou.

V3 záznamy sa renderujú **tými istými funkciami** ako FT prompt v maticiach
(`matrix_support.ft_case` + `testing_bodies_one_shot_v2.apply_profile`,
`refactoring_matrix.instruction`) a gold výstup je presne JSON, ktorý matice parsujú.
Testy v `tests/datasets/test_eval_aligned_v3.py` to overujú bajtovou zhodou promptu
a parsovaním gold výstupu cez `parse_testing_bodies` / `parse_answer`.

## Dáta

| Dataset | Zdroj | Výber |
|---|---|---|
| `data/processed/v3/testing` | Methods2Test **TRAIN** archív (`data/raw/methods2test/dataset/train.tar.bz2`), projektovo disjunktný s EVAL archívom matice | rovnaký screen ako eval (`infer_spec`, `general_wrap_record`), iba Jupiter-kompatibilné telá, dva rôzne gold testy tej istej focal metódy = `testCase1`/`testCase2`, max. 20 dvojíc na projekt |
| `data/processed/v3/refactoring` | MaRV train split + raw ML4Ref archívy | 11 operácií z kohorty (+ Inline Method), RefactoringMiner + rovnaké zarovnanie kontextu ako kohorta (`contextualize`), vylúčené commity/projekty/hashe kohorty a všetkých `test.jsonl` |
| `data/processed/v3/combined` | oba v3 datasety | vyvážené počtom riadkov (B1) |
| `data/processed/v3_onto/{testing,refactoring}` | ten istý build | tie isté záznamy, poradie, split a gold; inštrukcia navyše s blokom projektovej ontológie (`ontology.with_ontology`), rameno `ft_onto` |

**Spoločný manifest.** Builder pre každý záznam vyrobí obe verzie (v3 a v3_onto).
Záznam, pre ktorý blok ontológie zlyhá, alebo ktorého dlhšia verzia prekročí limit,
vypadne z **oboch**. Split sa robí raz. `manifest.json` (rovnaký v oboch priečinkoch)
obsahuje pre každé `case_id` split, hash gold výstupu a hashe oboch promptov. Kontrolný
v3 adaptér sa preto trénuje až z tohto buildu, nie zo staršieho. Potrebuje `rdflib`
(`pip install -e '.[ontology]'`).

Val split je projektovo disjunktný s train (`grouped_split_by_ratios`, 90/10).
Záznamy nad `--max-seq-length` (default = `max_seq_length` z model configu, 8192) sa
**zahodia**, nikdy neskracujú; počet je v `build_report.json`. Odhad z eval kohorty:
testing má ~1,3 tis. tokenov fixnej inštrukcie + trieda + 2 telá, teda ~2 tis., zahodí sa
prakticky nič; refactoring zarovnané kontextové jednotky (prompt + JSON výstup) majú
medián ~2,6 tis. a p90 ~5,8 tis. tokenov, pri 8192 sa zmestí ~96 % (91 z 95 eval
prípadov), pri 2048 iba ~35 %.

Tréningové configy `configs/finetuning/training_*_wsl.yaml` a model config sú teraz v3;
v2 sa reprodukuje z Git histórie a `config_snapshot.yaml` adaptérov.

Rozdiely voči eval, ktoré zostávajú (vedome):
- testing gold nie je overený kompiláciou ani JaCoCo (eval referencie áno);
- refactoring gold je celá „after“ kontextová jednotka, môže obsahovať aj iné zmeny
  z commitu (eval ich nehodnotí);
- 5 SWE prípadov používa projektovú šablónu inštrukcie (trieda + metóda), v3 trénuje
  iba štrukturálnu šablónu.

## Postup (WSL, koreň repa)

```bash
source .venv_wsl/bin/activate
python -m pytest -q tests/datasets/test_eval_aligned_v3.py tests/finetuning tests/ontology

# 1. Testing (archív TRAIN stiahni z Methods2Test vedľa eval.tar.bz2, ak chýba)
python scripts/datasets/prepare_v3_eval_aligned.py testing --max-records 20000   # smoke
python scripts/datasets/prepare_v3_eval_aligned.py testing

# 2. Refactoring (potrebuje JDK 17 + tools/refactoring-miner build ako príprava kohorty,
#    sieť pre MaRV súbory z GitHubu)
python scripts/datasets/prepare_v3_eval_aligned.py refactoring --max-archives 20  # smoke
python scripts/datasets/prepare_v3_eval_aligned.py refactoring

# 3. Shared mix
python scripts/datasets/prepare_v3_eval_aligned.py combined
```

Skontroluj `data/processed/v3/*/build_report.json`: počty, typy refactoringu,
`dropped_over_token_limit`, `dropped_ontology_failure`, dôvody zamietnutia. Over, že
`manifest.json` je v `v3/<task>` a `v3_onto/<task>` bajtovo rovnaký.

## Tréning

`max_seq_length` je 8192 (`configs/shared/models/qwen25_coder_7b_hf_wsl.yaml`).
Gradient checkpointing zapína `prepare_model_for_kbit_training`. Ak nestačí VRAM,
znížiť limit v model configu **aj** `--max-seq-length` pri builde a dataset prebudovať.

```bash
python scripts/finetuning/check_finetuning_ready.py --config configs/finetuning/training_b2_testing_wsl.yaml
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_testing_wsl.yaml --max_steps 2   # smoke
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_testing_wsl.yaml
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_refactoring_wsl.yaml
# ft_onto (rovnaké hyperparametre, dáta v3_onto)
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_testing_onto_wsl.yaml
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_refactoring_onto_wsl.yaml
```

Pred v3 tréningom bol tréningový skript nefunkčný: `run_training` volal
`load_base_model(model_config, quantization)` s dvoma argumentmi a loader čítal
`model.base_model`, ktorý HF model configy nemajú. `models/loader.py` teraz prijíma
oba tvary configu a kvantizáciu z `lora_config.yaml`.

## Matice na v3 (hotové)

Obe matice už používajú v3 adaptéry a ontologické ramená:

1. `configs/evaluation/eval_models.yaml` má `b2_testing_v3`, `b2_refactoring_v3`,
   `b2_testing_onto` a `b2_refactoring_onto` na
   `~/experiments/llm-ontology-v3/*/checkpoints/final_adapter`.
2. Plánové JSON mapujú každé FT rameno na adaptér (`adapters`); tréningové a validačné
   zdroje sú v3 aj v3_onto súbory. Freeze overí, že `training_summary.json` adaptéra
   nesie rovnaký názov experimentu a tieto zdroje.
3. Behy potrebujú nové `--run-id` (freeze hashuje zdrojové súbory aj adaptéry).
