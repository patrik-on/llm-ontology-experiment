# Úplné raw príklady používaných datasetov

Tento súbor ukazuje jeden **celý, neskrátený zdrojový záznam** z každého hlavného externého datasetu projektu: Methods2Test, ML4Refactoring a MaRV. Handcrafted smoke dataset je celý rozpísaný v `thesis_materials/handcrafted_skills/smoke_cases/handcrafted_smoke_all_cases.md`.

Pri JSON ukážkach bolo kvôli čitateľnosti zmenené iba odsadenie. Hodnoty, polia a obsah sú úplné; nikde nie je použité skracovanie `...`. Pri ML4Refactoring sú oba Java súbory načítané priamo zo zdrojového project ZIPu.

## Rýchle mapovanie zdroj → náš záznam

| Dataset | Čo je raw vstup | Čo je raw výstup | Čo pridávame my |
|---|---|---|---|
| Methods2Test | `src_fm` | `target` – developer-written JUnit test | inštrukcia, `domain`, `source`, `context_level`, proveniencia |
| ML4Refactoring | celý súbor v `before-refactoring` | celý súbor s rovnakou relatívnou cestou v `after-refactoring` | inštrukcia, `domain`, `source`, projekt, commit, cesta, typ z názvu súboru |
| MaRV | `code_before` | `code_after` | inštrukcia, `domain`, `source`, normalizované metadata a extrahované `evaluation_votes` |

## 1. Methods2Test

### Priama odpoveď: používame aj výstup datasetu?

**Áno.** Pole `target` sa pri preprocessingu preberá ako naše `output`. Je to referenčný test napísaný developerom, nie výstup, ktorý sme si synteticky vytvorili.

Použitie závisí od fázy:

- pri fine-tuningu je `src_fm` vstup a `target` cieľová odpoveď, z ktorej sa počíta loss;
- pri internej evaluácii je `target` referenčný výstup na porovnanie s predikciou, ale nie je súčasťou vstupného zadania modelu;
- pri RAG-u zostáva test v uloženom input/output príklade a môže sa modelu zobraziť ako demonštrácia. V aktuálnej V3 šablóne sa embedding vyhľadáva iba podľa vstupného production code, nie podľa referenčného testu.

Aktuálne používame najmenší kontext `src_fm`. Polia `src_fm_fc*` v raw zázname existujú, ale štandardná materializácia ich nepoužíva.

### Zdroj

`data/raw/methods2test/corpus/json/train/100021742/100021742_0_corpus.json`

### Celý raw záznam

```json
{
  "target": "@Test public void shouldGetPartitionAddress() { assertThat(NamingUtils.getPartitionAddress(\"testAddress\", 0)).isEqualTo(\"testAddress-0\"); }",
  "src_fm": "public static String getPartitionAddress(String address, int partition) { Objects.requireNonNull(address); return String.format(\"%s-%d\", address, partition); }",
  "src_fm_fc": "NamingUtils { public static String getPartitionAddress(String address, int partition) { Objects.requireNonNull(address); return String.format(\"%s-%d\", address, partition); } }",
  "src_fm_fc_co": "NamingUtils { public static String getPartitionAddress(String address, int partition) { Objects.requireNonNull(address); return String.format(\"%s-%d\", address, partition); }  }",
  "src_fm_fc_ms": "NamingUtils { public static String getPartitionAddress(String address, int partition) { Objects.requireNonNull(address); return String.format(\"%s-%d\", address, partition); }  static String getPartitionAddress(String address, int partition); static String getQueueName(String address, String group); static String getAnonymousGroupName(); }",
  "src_fm_fc_ms_ff": "NamingUtils { public static String getPartitionAddress(String address, int partition) { Objects.requireNonNull(address); return String.format(\"%s-%d\", address, partition); }  static String getPartitionAddress(String address, int partition); static String getQueueName(String address, String group); static String getAnonymousGroupName();  }"
}
```

### Význam a použitie každého poľa

Skratky sú kumulatívne: každá dlhšia reprezentácia obsahuje focal method a postupne k nej pridáva ďalší kontext focal class. `FM` znamená *focal method*, `FC` *focal class*, `CO` *constructor signatures*, `MS` *public method signatures* a `FF` *public fields*.

| Raw pole | Čo presne obsahuje a prečo existuje | Naše aktuálne použitie |
|---|---|---|
| `target` | Developerom napísaná testovacia metóda priradená k focal method. Je to referenčná odpoveď, ktorú sa má model naučiť generovať. | Preberáme ju ako `output`: tréningový cieľ, evaluačnú referenciu a obsah retrievaného demonštračného príkladu. |
| `src_fm` | Iba celá focal method: signatúra a telo metódy, ktorú test overuje. Je to najmenší a najťažší kontext, pretože neobsahuje zvyšok triedy. | Preberáme ju ako `input`; processed metadata dostane `context_level=src_fm`. |
| `src_fm_fc` | `FM + FC`: focal method vložená do obalu s názvom a deklaráciou focal class, napr. `NamingUtils { ... }`. Model tak pozná triedu, ku ktorej metóda patrí. | Nepoužívame v aktuálnej materializácii; je to dostupný variant pre experiment s väčším kontextom. |
| `src_fm_fc_co` | `FM + FC + CO`: predchádzajúci obsah plus signatúry konštruktorov focal class. Neobsahuje ich telá. Pomáha zistiť, ako sa dá testovaný objekt vytvoriť. | Aktuálne nepoužívame. |
| `src_fm_fc_ms` | `FM + FC + CO + MS`: navyše signatúry verejných metód focal class, spravidla bez tiel. Poskytuje informáciu o ďalších operáciách dostupných pri zostavení testu. | Aktuálne nepoužívame. |
| `src_fm_fc_ms_ff` | `FM + FC + CO + MS + FF`: najbohatší variant; navyše obsahuje verejné polia focal class. Model tak pozná aj stav alebo konštanty dostupné cez polia. | Aktuálne nepoužívame. |

V tejto konkrétnej ukážke `src_fm_fc` a `src_fm_fc_co` vyzerajú takmer rovnako, pretože zdroj pre `NamingUtils` neposkytol žiadny konštruktor. Podobne `src_fm_fc_ms` a `src_fm_fc_ms_ff` nemajú viditeľný rozdiel, pretože v zázname nie sú verejné polia. Názvy polí však stále označujú odlišné úrovne kontextu.

## 2. ML4Refactoring

ML4Refactoring neposkytuje jeden JSON objekt na príklad. Jeden logický raw záznam je **dvojica celých súborov** s rovnakou relatívnou cestou v adresároch `before-refactoring` a `after-refactoring`. Projekt a commit pochádzajú zo štruktúry adresárov; typ refaktoringu parsujeme z názvu súboru.

### Identita vybraného raw páru

| Pole | Hodnota |
|---|---|
| Project ZIP | `apache-abdera.zip` |
| Projekt | `abdera` |
| Commit | `77e8fe85a70c803dfff55cf4a3d0b8f929646607` |
| Relatívna cesta páru | `core/src/main/java/org/apache/abdera/util/NamedItem.java-1-Move Class-0-` |
| Typ odvodený z názvu | `Move Class` |
| Náš `input` | presný obsah súboru `before-refactoring` po `strip()` |
| Náš `output` | presný obsah súboru `after-refactoring` po `strip()` |

### Celá raw cesta – before

`output/abdera/storage/77e8fe85a70c803dfff55cf4a3d0b8f929646607/before-refactoring/core/src/main/java/org/apache/abdera/util/NamedItem.java-1-Move Class-0-`

### Celý raw súbor – before

```java
package org.apache.abdera;

public interface NamedItem {

    String getName();
}
```

### Celá raw cesta – after

`output/abdera/storage/77e8fe85a70c803dfff55cf4a3d0b8f929646607/after-refactoring/core/src/main/java/org/apache/abdera/util/NamedItem.java-1-Move Class-0-`

### Celý raw súbor – after

```java
package org.apache.abdera.util;

public interface NamedItem {

    String getName();
}
```

### Čo k páru dopĺňame

Doplníme slovenskú inštrukciu, `domain=refactoring`, `source=ml4refactoring`, `project=abdera`, commit SHA, relatívnu cestu a `refactoring_type=Move Class`. Pred uložením kontrolujeme neprázdnosť, rozdielnosť before/after a limity dĺžky.

## 3. MaRV

### Zdroj a identita

- súbor: `data/raw/marv/dataset/MaRV.json`
- top-level skupina: `Rename Method`
- `refactoring_id`: `189767`

### Celý raw záznam

```json
{
  "refactoring_id": "189767",
  "commit_sha": "8f6f447926d12a4607d38a864bf4c271e9e6ecf9",
  "commit_link": "https://github.com/osmandapp/osmand/commit/8f6f447926d12a4607d38a864bf4c271e9e6ecf9",
  "file_path": "OsmAnd/src/net/osmand/plus/mapcontextmenu/MenuController.java",
  "description": "Rename Method public fabVisible() : boolean renamed to public bottomButtonsVisible() : boolean in class net.osmand.plus.mapcontextmenu.MenuController",
  "code_before": "@@ -350,7 +350,7 @@ public boolean supportZoomIn() {\n \t\treturn true;\n \t}\n \n-\tpublic boolean fabVisible() {\n \t\treturn true;\n \t}\n \n",
  "code_after": "@@ -350,7 +350,7 @@ public boolean supportZoomIn() {\n \t\treturn true;\n \t}\n \n+\tpublic boolean bottomButtonsVisible() {\n \t\treturn true;\n \t}\n \n",
  "evaluations": [
    {
      "vote": 1
    },
    {
      "vote": 1
    }
  ]
}
```

### Presné mapovanie

| Raw pole | Naše použitie |
|---|---|
| top-level kľúč `Rename Method` | `refactoring_type` a súčasť inštrukcie |
| `code_before` | `input` |
| `code_after` | `output` |
| `refactoring_id` | zachovaná identita |
| `commit_sha`, `commit_link` | proveniencia; z linku odvodíme repository URL |
| `file_path`, `description` | zachované metadata |
| `evaluations` | zoznam manuálnych hodnotení; z každého objektu `{"vote": ...}` extrahujeme číslo do `evaluation_votes` |

### Čo presne znamená `evaluations`

Každá položka v `evaluations` je hlas jedného človeka, ktorý nezávisle videl before/after snippet a odpovedal na otázku, či dvojica skutočne predstavuje deklarovaný typ refaktoringu. MaRV plánovalo dve hodnotenia od dvoch rôznych reviewerov na jeden pár.

| Hodnota `vote` | Význam odpovede | Interpretácia |
|---:|---|---|
| `1` | **Agree** | reviewer súhlasí, že before/after pár predstavuje uvedený refaktoring; hlas podporuje true positive |
| `0` | **Disagree** | reviewer nesúhlasí; podľa neho ide o nesprávne detegovaný alebo nevhodne reprezentovaný refaktoring, teda false positive |
| `-1` | **I don't know** | reviewer sa nevedel spoľahlivo rozhodnúť; nejde o záporný hlas, ale o neurčité hodnotenie |

Vybraný záznam má `evaluations = [{"vote": 1}, {"vote": 1}]`. Obaja revieweri teda súhlasili, že zmena `fabVisible` → `bottomButtonsVisible` je Rename Method.

V našej lokálnej raw kópii má 693 záznamov dve hodnotenia a 5 záznamov iba jedno. Aktuálny preprocessing hlasy iba prepíše na zoznam, napr. `evaluation_votes=[1, 1]`; nevytvára z nich agregovaný label a podľa súhlasu reviewerov záznamy nefiltruje. Preto sa pri reportovaní musí rozlišovať jednomyseľné `1,1`, jednomyseľné `0,0`, konfliktné kombinácie a neurčité hlasy `-1`.

Význam hlasov a proces dvojitého hodnotenia opisuje primárny článok [MaRV: A Manually Validated Refactoring Dataset](https://labsoft-ufmg.github.io/publications/2025/forge2025preprint.pdf).

Dôležitá interpretačná poznámka: `code_before` a `code_after` sú v MaRV diff hunks, nie celé Java triedy.

## Ako tieto ukážky prezentovať

Najkratšia presná formulácia je: **externé datasety nám dávajú páry vstup–referenčný výstup; my ich obsahovo negenerujeme, ale validujeme, normalizujeme do jednej instruction schémy, dopĺňame provenienciu a pripravujeme splity pre fine-tuning, retrieval a evaluáciu.**
