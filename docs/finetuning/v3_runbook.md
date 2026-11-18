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

Val split je projektovo disjunktný s train (`grouped_split_by_ratios`, 90/10).
Záznamy nad `--max-seq-length` sa **zahodia**, nikdy neskracujú; počet je v
`build_report.json`.

Rozdiely voči eval, ktoré zostávajú (vedome):
- testing gold nie je overený kompiláciou ani JaCoCo (eval referencie áno);
- refactoring gold je celá „after“ kontextová jednotka, môže obsahovať aj iné zmeny
  z commitu (eval ich nehodnotí);
- 5 SWE prípadov používa projektovú šablónu inštrukcie (trieda + metóda), v3 trénuje
  iba štrukturálnu šablónu.

## Postup (WSL, koreň repa)

```bash
source .venv_wsl/bin/activate
python -m pytest -q tests/datasets/test_eval_aligned_v3.py tests/finetuning

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
`dropped_over_token_limit`, dôvody zamietnutia.

## Tréning

`max_seq_length` je 8192 (`configs/shared/models/qwen25_coder_7b_hf_wsl_v3.yaml`).
Gradient checkpointing zapína `prepare_model_for_kbit_training`. Ak nestačí VRAM,
znížiť limit v model configu **aj** `--max-seq-length` pri builde a dataset prebudovať.

```bash
python scripts/finetuning/check_finetuning_ready.py --config configs/finetuning/training_b2_testing_v3_wsl.yaml
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_testing_v3_wsl.yaml --max_steps 2   # smoke
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_testing_v3_wsl.yaml
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b2_refactoring_v3_wsl.yaml
python scripts/finetuning/train_finetuning.py --config configs/finetuning/training_b1_shared_v3_wsl.yaml
```

Pred v3 tréningom bol tréningový skript nefunkčný: `run_training` volal
`load_base_model(model_config, quantization)` s dvoma argumentmi a loader čítal
`model.base_model`, ktorý HF model configy nemajú. `models/loader.py` teraz prijíma
oba tvary configu a kvantizáciu z `lora_config.yaml`.

## Prepnutie matíc na v3 (follow-up, až keď adaptéry existujú)

Zámerne nie je v tomto kroku, lebo by rozbilo aktuálne prípravné behy:

1. `configs/benchmarks/java_evaluation_runtime_v1.yaml`: `hf_models_config:
   configs/evaluation/eval_models_v3.yaml`, `hf_model_name: b2_testing_v3`,
   `training_sources`/`validation_sources`/`checkpoint_selection_sources` na
   `data/processed/v3/testing/{train,val}.jsonl`.
2. `refactoring_matrix.runtime()`: `b2_refactoring_v3` a v3 refactoring súbory.
3. Nový `--run-id` pre obe matice (freeze hashuje zdrojové súbory aj adaptér).
4. Voliteľne rameno `ft_shared` (b1_shared_v3) a `qwen_base_hf` (bod D18 auditu).
