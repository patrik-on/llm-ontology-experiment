from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "datasets"

METHODS_RECORD = (
    ROOT
    / "data"
    / "raw"
    / "methods2test"
    / "corpus"
    / "json"
    / "train"
    / "100021742"
    / "100021742_0_corpus.json"
)
MARV_FILE = ROOT / "data" / "raw" / "marv" / "dataset" / "MaRV.json"
MARV_RECORD_ID = "189767"

ML4_ARCHIVE_NAME = "apache-abdera.zip"
ML4_PROJECT = "abdera"
ML4_COMMIT = "77e8fe85a70c803dfff55cf4a3d0b8f929646607"
ML4_RELATIVE_PATH = (
    "core/src/main/java/org/apache/abdera/util/"
    "NamedItem.java-1-Move Class-0-"
)
ML4_MEMBER_ROOT = f"output/{ML4_PROJECT}/storage/{ML4_COMMIT}"
ML4_BEFORE_MEMBER = f"{ML4_MEMBER_ROOT}/before-refactoring/{ML4_RELATIVE_PATH}"
ML4_AFTER_MEMBER = f"{ML4_MEMBER_ROOT}/after-refactoring/{ML4_RELATIVE_PATH}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build presentation-ready raw dataset and smoke-case documentation."
    )
    parser.add_argument(
        "--ml4-archive",
        type=Path,
        default=Path("C:/datasets/ml4refactoring/all/dataset") / ML4_ARCHIVE_NAME,
        help=f"Path to the source {ML4_ARCHIVE_NAME} project archive.",
    )
    return parser.parse_args()


def json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def code_block(language: str, value: str) -> str:
    return f"```{language}\n{value.rstrip()}\n```"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_zip_text(archive_path: Path, member: str) -> str:
    with zipfile.ZipFile(archive_path) as archive:
        try:
            payload = archive.read(member)
        except KeyError as exc:
            raise RuntimeError(f"Missing member {member!r} in {archive_path}") from exc
    return payload.decode("utf-8", errors="replace")


def find_marv_record(payload: dict[str, Any], refactoring_id: str) -> tuple[str, dict[str, Any]]:
    for refactoring_type, records in payload.items():
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict) and str(record.get("refactoring_id")) == refactoring_id:
                return refactoring_type, record
    raise RuntimeError(f"MaRV record {refactoring_id!r} was not found")


def build_raw_examples(ml4_archive: Path) -> str:
    methods_record = read_json(METHODS_RECORD)
    marv_type, marv_record = find_marv_record(read_json(MARV_FILE), MARV_RECORD_ID)
    ml4_before = read_zip_text(ml4_archive, ML4_BEFORE_MEMBER)
    ml4_after = read_zip_text(ml4_archive, ML4_AFTER_MEMBER)

    required_methods = {
        "target",
        "src_fm",
        "src_fm_fc",
        "src_fm_fc_co",
        "src_fm_fc_ms",
        "src_fm_fc_ms_ff",
    }
    if set(methods_record) != required_methods:
        raise RuntimeError("The selected Methods2Test example no longer has the expected fields")
    required_marv = {
        "refactoring_id",
        "commit_sha",
        "commit_link",
        "file_path",
        "description",
        "code_before",
        "code_after",
        "evaluations",
    }
    if set(marv_record) != required_marv:
        raise RuntimeError("The selected MaRV example no longer has the expected fields")

    parts = [
        "# Úplné raw príklady používaných datasetov",
        "",
        (
            "Tento súbor ukazuje jeden **celý, neskrátený zdrojový záznam** z každého "
            "hlavného externého datasetu projektu: Methods2Test, ML4Refactoring a MaRV. "
            "Handcrafted smoke dataset je celý rozpísaný v "
            "`docs/datasets/handcrafted_smoke_all_cases.md`."
        ),
        "",
        (
            "Pri JSON ukážkach bolo kvôli čitateľnosti zmenené iba odsadenie. Hodnoty, "
            "polia a obsah sú úplné; nikde nie je použité skracovanie `...`. Pri "
            "ML4Refactoring sú oba Java súbory načítané priamo zo zdrojového project ZIPu."
        ),
        "",
        "## Rýchle mapovanie zdroj → náš záznam",
        "",
        "| Dataset | Čo je raw vstup | Čo je raw výstup | Čo pridávame my |",
        "|---|---|---|---|",
        (
            "| Methods2Test | `src_fm` | `target` – developer-written JUnit test | "
            "inštrukcia, `domain`, `source`, `context_level`, proveniencia |"
        ),
        (
            "| ML4Refactoring | celý súbor v `before-refactoring` | celý súbor s rovnakou "
            "relatívnou cestou v `after-refactoring` | inštrukcia, `domain`, `source`, "
            "projekt, commit, cesta, typ z názvu súboru |"
        ),
        (
            "| MaRV | `code_before` | `code_after` | inštrukcia, `domain`, `source`, "
            "normalizované metadata a extrahované `evaluation_votes` |"
        ),
        "",
        "## 1. Methods2Test",
        "",
        "### Priama odpoveď: používame aj výstup datasetu?",
        "",
        (
            "**Áno.** Pole `target` sa pri preprocessingu preberá ako naše `output`. "
            "Je to referenčný test napísaný developerom, nie výstup, ktorý sme si "
            "synteticky vytvorili."
        ),
        "",
        "Použitie závisí od fázy:",
        "",
        (
            "- pri fine-tuningu je `src_fm` vstup a `target` cieľová odpoveď, z ktorej "
            "sa počíta loss;"
        ),
        (
            "- pri internej evaluácii je `target` referenčný výstup na porovnanie s "
            "predikciou, ale nie je súčasťou vstupného zadania modelu;"
        ),
        (
            "- pri RAG-u zostáva test v uloženom input/output príklade a môže sa modelu "
            "zobraziť ako demonštrácia. V aktuálnej V3 šablóne sa embedding vyhľadáva "
            "iba podľa vstupného production code, nie podľa referenčného testu."
        ),
        "",
        "Aktuálne používame najmenší kontext `src_fm`. Polia `src_fm_fc*` v raw zázname "
        "existujú, ale štandardná materializácia ich nepoužíva.",
        "",
        "### Zdroj",
        "",
        f"`{METHODS_RECORD.relative_to(ROOT).as_posix()}`",
        "",
        "### Celý raw záznam",
        "",
        json_block(methods_record),
        "",
        "### Význam a použitie každého poľa",
        "",
        (
            "Skratky sú kumulatívne: každá dlhšia reprezentácia obsahuje focal method "
            "a postupne k nej pridáva ďalší kontext focal class. `FM` znamená *focal "
            "method*, `FC` *focal class*, `CO` *constructor signatures*, `MS` *public "
            "method signatures* a `FF` *public fields*."
        ),
        "",
        "| Raw pole | Čo presne obsahuje a prečo existuje | Naše aktuálne použitie |",
        "|---|---|---|",
        (
            "| `target` | Developerom napísaná testovacia metóda priradená k focal "
            "method. Je to referenčná odpoveď, ktorú sa má model naučiť generovať. | "
            "Preberáme ju ako `output`: tréningový cieľ, evaluačnú referenciu a obsah "
            "retrievaného demonštračného príkladu. |"
        ),
        (
            "| `src_fm` | Iba celá focal method: signatúra a telo metódy, ktorú test "
            "overuje. Je to najmenší a najťažší kontext, pretože neobsahuje zvyšok "
            "triedy. | Preberáme ju ako `input`; processed metadata dostane "
            "`context_level=src_fm`. |"
        ),
        (
            "| `src_fm_fc` | `FM + FC`: focal method vložená do obalu s názvom a "
            "deklaráciou focal class, napr. `NamingUtils { ... }`. Model tak pozná "
            "triedu, ku ktorej metóda patrí. | Nepoužívame v aktuálnej materializácii; "
            "je to dostupný variant pre experiment s väčším kontextom. |"
        ),
        (
            "| `src_fm_fc_co` | `FM + FC + CO`: predchádzajúci obsah plus signatúry "
            "konštruktorov focal class. Neobsahuje ich telá. Pomáha zistiť, ako sa dá "
            "testovaný objekt vytvoriť. | Aktuálne nepoužívame. |"
        ),
        (
            "| `src_fm_fc_ms` | `FM + FC + CO + MS`: navyše signatúry verejných "
            "metód focal class, spravidla bez tiel. Poskytuje informáciu o ďalších "
            "operáciách dostupných pri zostavení testu. | Aktuálne nepoužívame. |"
        ),
        (
            "| `src_fm_fc_ms_ff` | `FM + FC + CO + MS + FF`: najbohatší variant; "
            "navyše obsahuje verejné polia focal class. Model tak pozná aj stav alebo "
            "konštanty dostupné cez polia. | Aktuálne nepoužívame. |"
        ),
        "",
        (
            "V tejto konkrétnej ukážke `src_fm_fc` a `src_fm_fc_co` vyzerajú takmer "
            "rovnako, pretože zdroj pre `NamingUtils` neposkytol žiadny konštruktor. "
            "Podobne `src_fm_fc_ms` a `src_fm_fc_ms_ff` nemajú viditeľný rozdiel, "
            "pretože v zázname nie sú verejné polia. Názvy polí však stále označujú "
            "odlišné úrovne kontextu."
        ),
        "",
        "## 2. ML4Refactoring",
        "",
        (
            "ML4Refactoring neposkytuje jeden JSON objekt na príklad. Jeden logický raw "
            "záznam je **dvojica celých súborov** s rovnakou relatívnou cestou v "
            "adresároch `before-refactoring` a `after-refactoring`. Projekt a commit "
            "pochádzajú zo štruktúry adresárov; typ refaktoringu parsujeme z názvu súboru."
        ),
        "",
        "### Identita vybraného raw páru",
        "",
        "| Pole | Hodnota |",
        "|---|---|",
        f"| Project ZIP | `{ML4_ARCHIVE_NAME}` |",
        f"| Projekt | `{ML4_PROJECT}` |",
        f"| Commit | `{ML4_COMMIT}` |",
        f"| Relatívna cesta páru | `{ML4_RELATIVE_PATH}` |",
        "| Typ odvodený z názvu | `Move Class` |",
        "| Náš `input` | presný obsah súboru `before-refactoring` po `strip()` |",
        "| Náš `output` | presný obsah súboru `after-refactoring` po `strip()` |",
        "",
        "### Celá raw cesta – before",
        "",
        f"`{ML4_BEFORE_MEMBER}`",
        "",
        "### Celý raw súbor – before",
        "",
        code_block("java", ml4_before),
        "",
        "### Celá raw cesta – after",
        "",
        f"`{ML4_AFTER_MEMBER}`",
        "",
        "### Celý raw súbor – after",
        "",
        code_block("java", ml4_after),
        "",
        "### Čo k páru dopĺňame",
        "",
        (
            "Doplníme slovenskú inštrukciu, `domain=refactoring`, "
            "`source=ml4refactoring`, `project=abdera`, commit SHA, relatívnu cestu a "
            "`refactoring_type=Move Class`. Pred uložením kontrolujeme neprázdnosť, "
            "rozdielnosť before/after a limity dĺžky."
        ),
        "",
        "## 3. MaRV",
        "",
        "### Zdroj a identita",
        "",
        f"- súbor: `{MARV_FILE.relative_to(ROOT).as_posix()}`",
        f"- top-level skupina: `{marv_type}`",
        f"- `refactoring_id`: `{MARV_RECORD_ID}`",
        "",
        "### Celý raw záznam",
        "",
        json_block(marv_record),
        "",
        "### Presné mapovanie",
        "",
        "| Raw pole | Naše použitie |",
        "|---|---|",
        "| top-level kľúč `Rename Method` | `refactoring_type` a súčasť inštrukcie |",
        "| `code_before` | `input` |",
        "| `code_after` | `output` |",
        "| `refactoring_id` | zachovaná identita |",
        "| `commit_sha`, `commit_link` | proveniencia; z linku odvodíme repository URL |",
        "| `file_path`, `description` | zachované metadata |",
        (
            "| `evaluations` | zoznam manuálnych hodnotení; z každého objektu "
            "`{\"vote\": ...}` extrahujeme číslo do `evaluation_votes` |"
        ),
        "",
        "### Čo presne znamená `evaluations`",
        "",
        (
            "Každá položka v `evaluations` je hlas jedného človeka, ktorý nezávisle "
            "videl before/after snippet a odpovedal na otázku, či dvojica skutočne "
            "predstavuje deklarovaný typ refaktoringu. MaRV plánovalo dve hodnotenia od "
            "dvoch rôznych reviewerov na jeden pár."
        ),
        "",
        "| Hodnota `vote` | Význam odpovede | Interpretácia |",
        "|---:|---|---|",
        (
            "| `1` | **Agree** | reviewer súhlasí, že before/after pár predstavuje "
            "uvedený refaktoring; hlas podporuje true positive |"
        ),
        (
            "| `0` | **Disagree** | reviewer nesúhlasí; podľa neho ide o nesprávne "
            "detegovaný alebo nevhodne reprezentovaný refaktoring, teda false positive |"
        ),
        (
            "| `-1` | **I don't know** | reviewer sa nevedel spoľahlivo rozhodnúť; "
            "nejde o záporný hlas, ale o neurčité hodnotenie |"
        ),
        "",
        (
            "Vybraný záznam má `evaluations = [{\"vote\": 1}, {\"vote\": 1}]`. "
            "Obaja revieweri teda súhlasili, že zmena `fabVisible` → "
            "`bottomButtonsVisible` je Rename Method."
        ),
        "",
        (
            "V našej lokálnej raw kópii má 693 záznamov dve hodnotenia a 5 záznamov "
            "iba jedno. Aktuálny preprocessing hlasy iba prepíše na zoznam, napr. "
            "`evaluation_votes=[1, 1]`; nevytvára z nich agregovaný label a podľa "
            "súhlasu reviewerov záznamy nefiltruje. Preto sa pri reportovaní musí "
            "rozlišovať jednomyseľné `1,1`, jednomyseľné `0,0`, konfliktné kombinácie "
            "a neurčité hlasy `-1`."
        ),
        "",
        (
            "Význam hlasov a proces dvojitého hodnotenia opisuje primárny článok "
            "[MaRV: A Manually Validated Refactoring Dataset]"
            "(https://labsoft-ufmg.github.io/publications/2025/forge2025preprint.pdf)."
        ),
        "",
        (
            "Dôležitá interpretačná poznámka: `code_before` a `code_after` sú v MaRV "
            "diff hunks, nie celé Java triedy."
        ),
        "",
        "## Ako tieto ukážky prezentovať",
        "",
        (
            "Najkratšia presná formulácia je: **externé datasety nám dávajú páry "
            "vstup–referenčný výstup; my ich obsahovo negenerujeme, ale validujeme, "
            "normalizujeme do jednej instruction schémy, dopĺňame provenienciu a "
            "pripravujeme splity pre fine-tuning, retrieval a evaluáciu.**"
        ),
        "",
    ]
    return "\n".join(parts)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise RuntimeError(f"Expected object in {path}:{line_number}")
            records.append(record)
    return records


def fixture_text(relative_path: str, expected_source: str | None = None) -> str:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if expected_source is not None and text.rstrip("\r\n") != expected_source.rstrip("\r\n"):
        raise RuntimeError(f"Fixture differs from source_code in {relative_path}")
    return text


def build_smoke_cases() -> str:
    testing_path = ROOT / "data" / "smoke" / "testing" / "cases.jsonl"
    refactoring_path = ROOT / "data" / "smoke" / "refactoring" / "cases.jsonl"
    testing = load_jsonl(testing_path)
    refactoring = load_jsonl(refactoring_path)
    if len(testing) != 12 or len(refactoring) != 12:
        raise RuntimeError("Expected exactly 12 testing and 12 refactoring smoke cases")
    all_ids = [str(record.get("id")) for record in testing + refactoring]
    if len(set(all_ids)) != 24:
        raise RuntimeError("Smoke case IDs are not unique")

    parts = [
        "# Všetky handcrafted smoke prípady na jednom mieste",
        "",
        (
            "Toto je prezentačný pohľad na **všetkých 24 ručne vytvorených smoke "
            "prípadov**: 12 pre generovanie testov a 12 pre refaktoring. Pri každom "
            "prípade je uvedený celý JSON záznam a celý obsah jeho fixture súborov. "
            "Nič nie je skrátené."
        ),
        "",
        "Zdrojom pravdy naďalej zostávajú:",
        "",
        "- `data/smoke/testing/cases.jsonl`,",
        "- `data/smoke/refactoring/cases.jsonl`,",
        "- `data/smoke/**/fixtures/`.",
        "",
        (
            "Tento súbor je odvodený prezentačný dokument. Smoke dataset sa nepoužíva "
            "na fine-tuning ani RAG a nesmie sa indexovať."
        ),
        "",
        "## Ako čítať obsah",
        "",
        (
            "Testing prípady nemajú jednu ručne napísanú „správnu JUnit odpoveď“. "
            "Namiesto exact-match oracle definujú celý vstup, požadované scenáre, "
            "výnimky, minimálny počet testov a validačné pravidlá. To umožňuje uznať "
            "viac rôznych, ale správnych testovacích implementácií."
        ),
        "",
        (
            "Refactoring prípady obsahujú ilustračný `reference_code` a samostatný "
            "`BehaviorTest.java`. Referenčný kód nie je exact-match oracle; rozhodujúca "
            "je kompilácia, behavior test, zachovanie API a štrukturálne očakávania."
        ),
        "",
        "## Čo z jedného záznamu dostáva model",
        "",
        (
            "Nie všetky riadky JSON záznamu sa posielajú modelu. Časť polí tvorí "
            "zadanie a zvyšok je skrytý evaluator-facing kontrakt, proveniencia alebo "
            "ochrana pred leakage. Toto oddelenie bráni tomu, aby prompt prezradil "
            "očakávané riešenie."
        ),
        "",
        "| Skupina údajov | Dostane model? | Ako ju používame |",
        "|---|---:|---|",
        (
            "| `input.source_code` | áno | hlavný Java vstup v prompte |"
        ),
        (
            "| `input.requirements` | áno | explicitné požiadavky pripojené k zadaniu |"
        ),
        (
            "| `input.class_name`, `focal_method` | áno | z nich skladáme stručný "
            "project context |"
        ),
        (
            "| testing `package_name`, `test_framework`, `imports` | áno, ak sú "
            "vyplnené | ďalší project context pre generovanie kompilovateľného testu |"
        ),
        (
            "| `task` a `input.kind` | nepriamo | vyberú testing alebo refactoring "
            "prompt, výstupnú schému a metriku |"
        ),
        (
            "| `expected_process`, `expected_output`, `validation_rules` | **nie** | "
            "skrytý kontrakt pre validáciu, interpretáciu a hodnotenie |"
        ),
        (
            "| `reference_code`, `BehaviorTest.java` | **nie** | referencia a behavior "
            "oracle; model ich v zadaní nevidí |"
        ),
        (
            "| ID, náročnosť, názov, tagy, poznámky, cesty a hashe | nie | výber "
            "prípadov, reportovanie, kontrola konzistencie a leakage audit |"
        ),
        "",
        "## Kompletný dátový slovník",
        "",
        "### Spoločné top-level polia každého prípadu",
        "",
        "| Pole | Čo znamená a prečo tam je | Ako ho používame |",
        "|---|---|---|",
        (
            "| `id` | Stabilný unikátny identifikátor v tvare "
            "`<task>_<difficulty>_<NNN>`. | Výber konkrétneho prípadu, `case_id`, "
            "`run_id`, párovanie výsledkov a kontrola duplicít. |"
        ),
        (
            "| `task` | Hodnota `testing` alebo `refactoring`. | Prepína prompt, "
            "štruktúrovaný modelový výstup, retrieval filter a sadu metrík. Musí sa "
            "zhodovať s `input.kind` aj `expected_output.kind`. |"
        ),
        (
            "| `difficulty` | Ručne pridelená úroveň `easy`, `medium` alebo `tricky`. | "
            "Vyváženie datasetu, filtrovanie experimentov a report výsledkov podľa "
            "náročnosti; model ju v prompte nevidí. |"
        ),
        (
            "| `title` | Krátky ľudsky čitateľný názov prípadu. | Tabuľky, reporty a "
            "orientácia človeka; nie promptová požiadavka. |"
        ),
        (
            "| `input` | Vnorený objekt opisujúci modelový vstup a jeho fixtures. | "
            "Loader ho podľa `kind` validuje ako testing alebo refactoring vstup. |"
        ),
        (
            "| `expected_process` | Krátke kroky, ktoré opisujú rozumný spôsob "
            "vyriešenia prípadu. | Pomôcka pre človeka/evaluátora a audit pokrytia; "
            "nikdy sa neposiela modelu a nepovažuje sa za požadovaný chain-of-thought. |"
        ),
        (
            "| `expected_output` | Strojovo čitateľný kontrakt toho, čo má úspešný "
            "výstup spĺňať. | Kontrola schémy a konzistencie, tvorba referencie pri "
            "refactoringu a interpretácia výsledkov; je skrytý pred modelom. |"
        ),
        (
            "| `validation_rules` | Zoznam konkrétnych kontrol vo forme "
            "`{rule, value}`. | Deklaruje hodnotiaci checklist a umožňuje overiť, že "
            "prípad má povinné kritériá. Nejde o text promptu. |"
        ),
        (
            "| `tags` | Tematické značky, napr. `boundary`, `exception`, "
            "`extract-method`. | Kategorizácia, analýza pokrytia a ľudská navigácia; "
            "aktuálne nie sú súčasťou promptu. |"
        ),
        (
            "| `notes` | Doplňujúce interpretačné upozornenie alebo povolená "
            "alternatíva. | Dokumentácia pre evaluátora; model ju nevidí. |"
        ),
        (
            "| `input_code_hash` | SHA-256 presných UTF-8 bajtov "
            "`input.source_code`, citlivý aj na whitespace. | Odhalenie nechcenej "
            "zmeny dát a kontrola zhody uloženého záznamu. |"
        ),
        (
            "| `normalized_input_code_hash` | SHA-256 lexikálne normalizovaného Java "
            "vstupu: ignoruje komentáre a formátovací whitespace, ale zachováva tokeny "
            "a string literály. | Deduplikácia a leakage kontrola aj pri inom "
            "formátovaní rovnakého kódu. |"
        ),
        (
            "| `focal_method_hash` | Rovnaký normalizovaný hash, ale iba pre presne "
            "jednu metódu pomenovanú v `input.focal_method`. | Kontrola unikátnosti a "
            "odhalenie overlapu tej istej focal method v iných datasetoch. |"
        ),
        "",
        "### Polia v `input` spoločné pre obe úlohy",
        "",
        "| Pole | Čo znamená a prečo tam je | Ako ho používame |",
        "|---|---|---|",
        (
            "| `kind` | Diskriminátor `testing`/`refactoring` pre vnorenú schému. | "
            "Pydantic podľa neho zvolí správny typ objektu; musí sedieť s `task`. |"
        ),
        (
            "| `class_name` | Názov Java triedy vo `source_code`. | Posiela sa v "
            "project context a používa sa v identite prípadu. |"
        ),
        (
            "| `source_code` | Celý Java zdroj, na ktorom má model pracovať. | Je to "
            "hlavný `input_text` promptu; musí sa kódovo zhodovať s obsahom "
            "`Input.java`. |"
        ),
        (
            "| `focal_method` | Primárna metóda, na ktorú je úloha zameraná. | "
            "Posiela sa v project context, testing metriky kontrolujú proxy jej volania "
            "a z metódy sa počíta `focal_method_hash`. |"
        ),
        (
            "| `requirements` | Ľudsky napísané požiadavky a hranice konkrétnej "
            "úlohy. | Pripájajú sa priamo do kanonického promptu vo všetkých režimoch, "
            "aby Direct, RAG a MultiRAG dostali rovnaké zadanie. |"
        ),
        (
            "| `fixture_path` | Cesta k samostatnému `Input.java`. | Dataset validator "
            "overí existenciu a obsahovú zhodu so `source_code` po orezaní okrajového "
            "whitespace; cesta sa modelu neposiela. |"
        ),
        "",
        "### Dodatočné testing polia v `input`",
        "",
        "| Pole | Čo znamená a prečo tam je | Ako ho používame |",
        "|---|---|---|",
        (
            "| `test_framework` | Požadovaný framework; schéma povoľuje `JUnit 5`. | "
            "Uvádza sa v project context a očakávaný výstup ho musí rešpektovať. |"
        ),
        (
            "| `package_name` | Package testovanej triedy; prázdny reťazec znamená "
            "default package. | Ak je vyplnený, pridá sa do project contextu, aby model "
            "vytvoril správnu package deklaráciu. |"
        ),
        (
            "| `imports` | Importy, ktoré používa vstupný Java zdroj. | Ak zoznam nie "
            "je prázdny, zobrazí sa modelu ako declared imports a pomáha pri "
            "kompilovateľnosti testu. |"
        ),
        "",
        "### Dodatočné refactoring pole v `input`",
        "",
        "| Pole | Čo znamená a prečo tam je | Ako ho používame |",
        "|---|---|---|",
        (
            "| `behavior_test_path` | Cesta k ručne napísanému JUnit "
            "`BehaviorTest.java`, ktorý kodifikuje pozorovateľné správanie. | Nie je v "
            "prompte. Offline validator ho spúšťa nad pôvodným vstupom aj nad "
            "`reference_code`, aby overil korektnosť smoke prípadu. |"
        ),
        "",
        "### Testing polia v `expected_output`",
        "",
        "| Pole | Čo znamená a prečo tam je | Ako ho používame |",
        "|---|---|---|",
        (
            "| `kind` | Hodnota `testing`, diskriminátor výstupnej schémy. | Kontrola "
            "zhody s `task` a `input.kind`. |"
        ),
        (
            "| `must_compile` | Výstup musí byť kompilovateľný Java zdroj. | Povinný "
            "kontrakt; každý smoke prípad ho má `true`. |"
        ),
        (
            "| `must_use_framework` | Framework, ktorý má generovaný test používať. | "
            "Musí byť `JUnit 5` a zodpovedá `input.test_framework`. |"
        ),
        (
            "| `must_call_method` | Metóda, ktorú musí test reálne zavolať. | Musí sa "
            "zhodovať s `input.focal_method`; testing metriky počítajú regexový proxy "
            "indikátor jej volania. |"
        ),
        (
            "| `minimum_test_methods` | Minimálny požadovaný počet testovacích metód. | "
            "Per-case prah a súčasť validation kontraktu; metriky reportujú proxy počet "
            "testovacích metód. |"
        ),
        (
            "| `required_scenarios` | Konkrétne behaviorálne a hraničné scenáre, ktoré "
            "majú testy pokryť. | Checklist pre hodnotenie pokrytia; model ich nevidí, "
            "aby neunikla evaluator-facing referencia. |"
        ),
        (
            "| `expected_exception_types` | Presné Java exception typy, pre ktoré sa "
            "očakáva exception test. Prázdny zoznam znamená, že taká požiadavka nie je. | "
            "Musí byť v súlade s pravidlom `expected_exception_asserted`; metriky "
            "reportujú prítomnosť exception-test konštrukcie. |"
        ),
        "",
        "### Refactoring polia v `expected_output`",
        "",
        "| Pole | Čo znamená a prečo tam je | Ako ho používame |",
        "|---|---|---|",
        (
            "| `kind` | Hodnota `refactoring`, diskriminátor výstupnej schémy. | "
            "Kontrola zhody s `task` a `input.kind`. |"
        ),
        (
            "| `expected_refactoring_types` | Jeden alebo viac očakávaných typov zmeny, "
            "napr. `Extract Method`. | Klasifikácia prípadu a interpretačný kontrakt; "
            "nevynucujeme exact textovú zhodu riešenia. |"
        ),
        (
            "| `must_compile` | Refaktorovaný výstup musí byť kompilovateľný. | "
            "Povinný kontrakt s hodnotou `true`. |"
        ),
        (
            "| `must_preserve_behavior` | Refaktoring nesmie zmeniť pozorovateľné "
            "správanie. | Zdôvodňuje behavior oracle a pravidlo "
            "`behavior_tests_pass`. |"
        ),
        (
            "| `must_preserve_public_api` | Verejné signatúry požadované zadaním sa "
            "nesmú zmeniť. | Kontrakt kontrolovaný cez príslušné pravidlo a behavior "
            "fixtures; model ho dostáva aj všeobecne v refactoring inštrukcii. |"
        ),
        (
            "| `structural_expectations` | Zoznam očakávaných štrukturálnych vlastností "
            "výsledku, napr. existencia helper metódy alebo odstránenie duplicity. | "
            "Užšie hodnotiace kritériá bez požiadavky na identický text. |"
        ),
        (
            "| `reference_code` | Jedna ručne napísaná ilustračná správna "
            "refaktorovaná verzia. | Experiment runner ju používa ako referenčný "
            "výstup pre podobnostné a code-health metriky; offline validator ju "
            "kompiluje a spúšťa s `BehaviorTest.java`. Model ju nevidí. |"
        ),
        "",
        "### Polia objektu v `validation_rules`",
        "",
        "| Pole | Čo znamená | Ako ho používame |",
        "|---|---|---|",
        (
            "| `rule` | Strojový názov kontroly zo zoznamu povolených pravidiel. | "
            "Loader odmietne neznáme názvy a validator kontroluje povinné pravidlá pre "
            "danú úlohu. |"
        ),
        (
            "| `value` | Parameter pravidla: názov metódy, počet, exception typ, "
            "zoznam scenárov alebo štrukturálny cieľ. `null` znamená, že samotná "
            "prítomnosť pravidla vyjadruje boolean požiadavku. | Umožňuje porovnať "
            "konkrétnu požiadavku s `expected_output` a neskôr ju automatizovať. |"
        ),
        "",
        "### Význam všetkých názvov `validation_rules.rule`",
        "",
        "| Pravidlo | Čo požaduje | Stav použitia v aktuálnej pipeline |",
        "|---|---|---|",
        (
            "| `code_compiles` | Java vstup/výstup sa má skompilovať. | Povinné v "
            "schéme; offline dataset validator kompiluje vstupy a referenčné riešenia. |"
        ),
        (
            "| `generated_tests_pass` | Vygenerované JUnit testy sa majú spustiť bez "
            "zlyhania nad testovanou triedou. | Povinný testing kontrakt; súčasný "
            "experiment runner zatiaľ reportuje hlavne textové/štrukturálne proxy "
            "metriky a toto pravidlo nad každou modelovou predikciou automaticky "
            "nespúšťa. |"
        ),
        (
            "| `invokes_focal_method` | Test musí volať metódu uvedenú vo `value`. | "
            "Hodnota sa validuje voči `must_call_method`; runner reportuje regexový "
            "`target_method_invocation_proxy`. |"
        ),
        (
            "| `minimum_test_methods` | Výstup má aspoň počet testovacích metód vo "
            "`value`. | Kontrakt sa zhoduje s `expected_output`; runner reportuje "
            "`test_method_count_proxy`, no per-case prah zatiaľ samostatne nevyhodnocuje. |"
        ),
        (
            "| `required_scenarios` | Testy majú pokryť kategórie uvedené vo `value`. | "
            "Evaluator-facing checklist; automatické semantické overenie všetkých "
            "scenárov zatiaľ nie je implementované. |"
        ),
        (
            "| `expected_exception_asserted` | Test má asertovať presný exception typ vo "
            "`value`. | Kontroluje sa konzistencia dát; runner reportuje všeobecný "
            "`has_exception_test`, nie vždy presný typ. |"
        ),
        (
            "| `public_api_preserved` | Refaktoring nesmie porušiť požadované verejné "
            "signatúry. | Povinný refactoring kontrakt; deklarované kritérium pre "
            "behavior/API validáciu. |"
        ),
        (
            "| `behavior_tests_pass` | Výsledok musí prejsť priloženým behavior testom. | "
            "Offline validator ho overuje na vstupe a `reference_code`; súčasný smoke "
            "experiment runner ho ešte nespúšťa nad každou modelovou predikciou. |"
        ),
        (
            "| `helper_method_exists` | Po Extract Method má existovať helper uvedený vo "
            "`value`. | Štrukturálny kontrakt/checklist; zatiaľ nie samostatná runtime "
            "metrika. |"
        ),
        (
            "| `focal_method_shorter` | Pôvodná focal method má byť po extrakcii kratšia. | "
            "Štrukturálny kontrakt; code metrics reportujú dĺžkové proxy, ale pravidlo "
            "sa nevyhodnocuje ako samostatné pass/fail. |"
        ),
        (
            "| `dead_code_removed` | Uvedený nepoužívaný kód alebo identifikátor má "
            "zmiznúť. | Štrukturálny checklist pre Remove Dead Code. |"
        ),
        (
            "| `boolean_expression_simplified` | Boolean logika má byť jednoduchšia pri "
            "zachovaní správania. | Štrukturálny checklist; všeobecné code-health "
            "metriky zachytia iba proxy zmenu. |"
        ),
        (
            "| `identifier_renamed` | Identifikátor má byť premenovaný alebo odstránený "
            "podľa `value`. | Úzke štrukturálne očakávanie, zatiaľ bez samostatného "
            "automatického pass/fail evaluátora. |"
        ),
        (
            "| `duplication_reduced` | Opakovaný fragment sa má zdieľať alebo extrahovať. | "
            "Štrukturálny checklist; súčasné metriky používajú iba všeobecné proxy. |"
        ),
        "",
        "## Čo predstavujú priložené Java súbory",
        "",
        "| Súbor | Účel | Dostane ho model? |",
        "|---|---|---:|",
        (
            "| `Input.java` | Kanonická súborová kópia `input.source_code`; umožňuje "
            "reálnu kompiláciu mimo JSONL. | jeho obsah áno, cesta nie |"
        ),
        (
            "| `BehaviorTest.java` | Ručne napísaný JUnit oracle pre zachovanie správania "
            "refactoring prípadu. | nie |"
        ),
        "",
        "## Dôležité obmedzenie aktuálnej automatizácie",
        "",
        (
            "Dáta už obsahujú bohatší hodnotiaci kontrakt, než dnes automaticky vykonáva "
            "experiment runner. Loader a offline validator kontrolujú schému, hashe, "
            "distribúciu, zhodu fixtures, kompiláciu vstupov a behavior testy pôvodného "
            "aj referenčného refactoring kódu. Bežný smoke experiment však pri modelových "
            "predikciách momentálne počíta hlavne generické testing/refactoring proxy "
            "metriky. `validation_rules` preto treba reportovať ako deklarovaný kontrakt; "
            "nie všetky jeho položky sú už automatický pass/fail test modelového výstupu."
        ),
        "",
        "## Ako aktuálne hodnotíme modelový výstup",
        "",
        (
            "Handcrafted smoke evaluácia má dve rozdielne vetvy. Testing vetva vyberie "
            "z modelovej odpovede `generated_tests`; refactoring vetva vyberie "
            "`refactored_code`. Nasledujúce diagramy zobrazujú **aktuálnu "
            "implementáciu**, nie iba plánovaný kontrakt."
        ),
        "",
        "### Testing: aktuálne hodnotenie `generated_tests`",
        "",
        "```text",
        "                  Generated test",
        "                        │",
        "       ┌────────────────┼─────────────────┐",
        "       ▼                ▼                 ▼",
        "  response validity   structure       heuristic quality",
        "       │                │                 │",
        "  valid JSON/schema    @Test present    trivial-test smell",
        "  non-empty code       assertions       quality score 0–10",
        "                       test count       coverage proxy label",
        "                       focal call       low / medium / high",
        "                       exception test",
        "                       mocking proxy",
        "```",
        "",
        "Konkrétne testing metriky:",
        "",
        "| Oblasť | Metrika | Čo reálne kontroluje |",
        "|---|---|---|",
        (
            "| základ výstupu | `output_non_empty` | či model vrátil neprázdny Java "
            "text v poli `generated_tests` |"
        ),
        (
            "| veľkosť | `prediction_char_length`, `prediction_token_count` | dĺžka "
            "odpovede; sama osebe nehovorí o správnosti |"
        ),
        (
            "| testová štruktúra | `contains_test_annotation` | text obsahuje `@Test` |"
        ),
        (
            "| testová štruktúra | `test_method_count_proxy` | regexový odhad počtu "
            "testovacích metód |"
        ),
        (
            "| assertions | `assertion_count`, `has_assertion` | počet známych assertion "
            "volaní, napr. `assertEquals`, `assertThrows`, `assertThat` |"
        ),
        (
            "| zameranie | `target_method_invocation_proxy` | regexom zisťuje, či test "
            "pravdepodobne volá focal method |"
        ),
        (
            "| výnimky | `has_exception_test` | hľadá `assertThrows`, `catch`, `throws` "
            "alebo podobnú exception-test konštrukciu |"
        ),
        (
            "| mocking | `has_mocking` | hľadá Mockito/mock/when/verify konštrukcie; je "
            "to opisná metrika, nie automaticky plus alebo mínus |"
        ),
        (
            "| smell | `trivial_test_smell` | penalizuje prázdny test alebo triviálne "
            "assertions typu `assertTrue(true)` |"
        ),
        (
            "| agregácia | `generated_test_quality_score` | heuristický súčet vyššie "
            "uvedených signálov v rozsahu 0–10 |"
        ),
        (
            "| agregácia | `coverage_proxy_score/label` | rovnaký heuristický score "
            "prevedený na `invalid/low/medium/high`; **nejde o skutočné code coverage** |"
        ),
        "",
        (
            "`generated_test_quality_score` prideľuje +1 za neprázdny výstup, +2 za "
            "`@Test`, +2 za aspoň jednu assertion, +2 za proxy volania focal method, "
            "+1 za exception test a +1 za viac assertions alebo testovacích metód. "
            "Triviálny test odpočíta 3 body a prázdny výstup 5; výsledok sa oreže na "
            "0–10. Coverage label je `high` od 7, `medium` od 4, `low` nad 0 a "
            "`invalid` pri 0."
        ),
        "",
        (
            "Runner technicky uloží aj `exact_match`, `normalized_exact_match` a edit "
            "similarity. Testing prípady však zámerne nemajú `reference_output`, takže "
            "tieto reference-based hodnoty pri testing smoke nie sú zmysluplnou mierou "
            "kvality a nemajú sa reportovať ako úspešnosť."
        ),
        "",
        "### Čo testing vetva dnes ešte nerobí",
        "",
        "```text",
        "                  Generated test",
        "                        │",
        "        ┌───────────────┼────────────────┐",
        "        ▼               ▼                ▼",
        "     compilation      execution       test strength",
        "        │               │                │",
        "    compile@1        JUnit pass@1      line/branch coverage",
        "                                        mutation score",
        "                                        real bug detection",
        "",
        "             NOT YET EXECUTED ON MODEL OUTPUT",
        "```",
        "",
        (
            "To znamená, že dnešný `coverage_proxy` sa nesmie prezentovať ako JaCoCo "
            "line/branch coverage. Rovnako dnes pre modelový test nemáme reálne "
            "`compile@1`, `pass@1`, mutation score ani počet odhalených bugov. Tieto "
            "požiadavky sú čiastočne pripravené v `expected_output` a "
            "`validation_rules`, ale smoke runner ich zatiaľ všetky nevykonáva."
        ),
        "",
        "### Refactoring: aktuálne hodnotenie `refactored_code`",
        "",
        "```text",
        "                 Refactored code",
        "                        │",
        "       ┌────────────────┼──────────────────┐",
        "       ▼                ▼                  ▼",
        "  response validity   reference          code-health proxies",
        "       │              comparison                 │",
        "  valid JSON/schema   edit similarity      complexity delta",
        "  non-empty code      exact-match info     nesting delta",
        "  differs from input                       method-length delta",
        "                                           cohesion proxy",
        "                                           coupling proxy",
        "                                           quality score 0–10",
        "```",
        "",
        "Konkrétne refactoring hodnotenie rieši:",
        "",
        "| Oblasť | Čo meriame | Interpretácia |",
        "|---|---|---|",
        (
            "| platnosť odpovede | neprázdny `refactored_code`, zmena oproti vstupu | "
            "model musí vrátiť kód a nesmie iba zopakovať vstup |"
        ),
        (
            "| referencia | normalized edit similarity k `reference_code` | podobnosť s "
            "jednou ručne napísanou variantou; iné behaviorálne ekvivalentné riešenie "
            "môže mať nižšie skóre |"
        ),
        (
            "| veľkosť a štruktúra | LOC, počet metód/tried/importov, priemerná a "
            "maximálna dĺžka metód, parametre a lokálne premenné | opis štrukturálnej "
            "zmeny pred/po |"
        ),
        (
            "| zložitosť | počty `if`, cyklov, `case`, `catch`, logických operátorov a "
            "`complexity_proxy_score` | heuristická zmena riadiacej zložitosti |"
        ),
        (
            "| vnorenie | `max_brace_nesting_depth` a jeho delta | či refaktoring "
            "sploštil alebo prehĺbil štruktúru |"
        ),
        (
            "| kvalita návrhu | `cohesion_proxy_score`, `coupling_proxy_score` | "
            "heuristické, nie statickým analyzátorom potvrdené cohesion/coupling |"
        ),
        (
            "| agregácia | `code_health_delta_score`, `refactoring_quality_score` | "
            "kombinované proxy skóre 0–10 |"
        ),
        "",
        (
            "`refactoring_quality_score` kombinuje: 1,5 bodu za zmenu oproti vstupu, "
            "až 2,5 bodu za podobnosť s referenciou, 25 % z `code_health_delta_score`, "
            "20 % z cohesion proxy a bonus za nižší coupling proxy; výsledok sa oreže "
            "na 0–10. Vysoké skóre preto znamená dobrú kombináciu textovej podobnosti a "
            "heuristických code metrík, nie automaticky dokázanú behaviorálnu korektnosť."
        ),
        "",
        "### Čo refactoring vetva dnes ešte nerobí",
        "",
        "```text",
        "                 Refactored code",
        "                        │",
        "       ┌────────────────┼──────────────────┐",
        "       ▼                ▼                  ▼",
        "    compilation       behavior         exact constraints",
        "       │                │                  │",
        "    compile@1       BehaviorTest pass   public API diff",
        "                                         helper exists",
        "                                         rename/dead code",
        "                                         duplication reduced",
        "",
        "             NOT YET EXECUTED ON MODEL OUTPUT",
        "```",
        "",
        (
            "Aktuálny runner teda nekompiluje každú modelovú refactoring predikciu a "
            "nespúšťa nad ňou príslušný `BehaviorTest.java`. Rovnako jednotlivé "
            "štrukturálne `validation_rules` ešte nemajú samostatný automatický "
            "pass/fail výsledok."
        ),
        "",
        "### Čo validujeme offline ešte pred experimentom",
        "",
        "```text",
        "              Handcrafted smoke case",
        "                        │",
        "          ┌─────────────┴─────────────┐",
        "          ▼                           ▼",
        "     testing input              refactoring pair",
        "          │                           │",
        "    Input.java compiles       Input.java compiles",
        "                              reference_code compiles",
        "                              BehaviorTest passes before",
        "                              BehaviorTest passes after",
        "```",
        "",
        (
            "Toto offline overenie dokazuje, že ručne vytvorený benchmarkový prípad a "
            "jeho referencia sú konzistentné. **Nedokazuje však**, že rovnakými "
            "kontrolami prešiel modelový výstup; to je samostatná chýbajúca vrstva."
        ),
        "",
        "### Čo teda handcrafted smoke hodnotenie dnes rieši",
        "",
        "- či funguje celý Direct/RAG/MultiRAG inference a reporting tok,",
        "- či model vráti správnu štruktúrovanú odpoveď a neprázdny Java kód,",
        "- či generovaný test vyzerá ako netriviálny JUnit test a volá focal method,",
        "- či refaktoring niečo zmenil a ako sa zmenili proxy ukazovatele kódu,",
        "- či je výstup podobný ručne napísanej refactoring referencii,",
        "- porovnanie rovnakých prípadov medzi No-RAG, Single-RAG a MultiRAG režimom.",
        "",
        (
            "Na tvrdenie o funkčnej korektnosti testov alebo refaktoringu však treba "
            "doplniť kompiláciu modelového výstupu, reálne spustenie JUnit/BehaviorTest, "
            "coverage a pri test generation ideálne mutation testing alebo bug-detection "
            "benchmark."
        ),
        "",
        "## Obsah",
        "",
        "| ID | Úloha | Náročnosť | Názov |",
        "|---|---|---|---|",
    ]
    for record in testing + refactoring:
        parts.append(
            f"| `{record['id']}` | `{record['task']}` | `{record['difficulty']}` | "
            f"{record['title']} |"
        )

    sections = (("Testing", testing), ("Refactoring", refactoring))
    for section_name, records in sections:
        parts.extend(["", f"# {section_name}: {len(records)} prípadov", ""])
        for index, record in enumerate(records, start=1):
            case_id = str(record["id"])
            title = str(record["title"])
            fixture_path = str(record["input"]["fixture_path"])
            input_java = fixture_text(
                fixture_path,
                expected_source=str(record["input"]["source_code"]),
            )
            parts.extend(
                [
                    f"## {index}. `{case_id}` — {title}",
                    "",
                    f"- úloha: `{record['task']}`",
                    f"- náročnosť: `{record['difficulty']}`",
                    f"- tagy: `{', '.join(record['tags'])}`",
                    "",
                    "### Celý JSONL záznam",
                    "",
                    json_block(record),
                    "",
                    f"### Celý `{fixture_path}`",
                    "",
                    code_block("java", input_java),
                    "",
                ]
            )
            behavior_path = record["input"].get("behavior_test_path")
            if behavior_path:
                behavior_path = str(behavior_path)
                parts.extend(
                    [
                        f"### Celý `{behavior_path}`",
                        "",
                        code_block("java", fixture_text(behavior_path)),
                        "",
                    ]
                )

    return "\n".join(parts)


def main() -> None:
    args = parse_args()
    ml4_archive = args.ml4_archive.resolve()
    if not ml4_archive.is_file():
        raise FileNotFoundError(f"ML4Refactoring archive not found: {ml4_archive}")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = DOCS_DIR / "raw_record_examples.md"
    smoke_path = DOCS_DIR / "handcrafted_smoke_all_cases.md"
    raw_path.write_text(build_raw_examples(ml4_archive), encoding="utf-8", newline="\n")
    smoke_path.write_text(build_smoke_cases(), encoding="utf-8", newline="\n")
    print(f"Wrote {raw_path.relative_to(ROOT).as_posix()}")
    print(f"Wrote {smoke_path.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
