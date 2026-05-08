# Dataset Samples

Tento priečinok ukazuje malé reprezentatívne snippety z datasetov bez commitovania plných JSONL splitov.

Plné datasety sú v `data/processed/`, ale sú ignorované Gitom:

- `testing/`: Methods2Test pre generovanie JUnit testov,
- `refactoring_ml4ref/`: ML4Refactoring refactoring páry,
- `refactoring_marv/`: MaRV refactoring páry,
- `refactoring/`: finálny B2-R refactoring dataset,
- `combined/`: finálny B1 shared dataset.

## Instruction-Tuning Formát

Každý reálny záznam má minimálne:

```json
{
  "instruction": "...",
  "input": "...",
  "output": "...",
  "domain": "testing alebo refactoring",
  "source": "methods2test / ml4refactoring / marv"
}
```

Refactoring záznamy majú často aj:

```json
{
  "project": "...",
  "commit_sha": "...",
  "file_path": "...",
  "refactoring_type": "Rename Method"
}
```

## Testing Príklad

Zdroj: `data/processed/testing/train.jsonl`

```json
{
  "instruction": "Vygeneruj JUnit test pre nasledujúcu Java metódu.",
  "input": "public static String getPartitionAddress(String address, int partition) { Objects.requireNonNull(address); return String.format(\"%s-%d\", address, partition); }",
  "output": "@Test public void shouldGetPartitionAddress() { assertThat(NamingUtils.getPartitionAddress(\"testAddress\", 0)).isEqualTo(\"testAddress-0\"); }",
  "domain": "testing",
  "source": "methods2test",
  "context_level": "src_fm"
}
```

## ML4Refactoring Príklad

Zdroj: `data/processed/refactoring_ml4ref/train.jsonl`

```json
{
  "instruction": "Vygeneruj refaktorovanú verziu nasledujúceho Java kódu podľa typu refaktoringu: Rename Method.",
  "input": "public int getDiscarded() { TopicSubscription topicSubscription = getTopicSubscription(); return topicSubscription != null ? topicSubscription.discarded() : 0; }",
  "output": "public int getDiscardedCount() { TopicSubscription topicSubscription = getTopicSubscription(); return topicSubscription != null ? topicSubscription.discarded() : 0; }",
  "domain": "refactoring",
  "source": "ml4refactoring",
  "project": "activemq",
  "refactoring_type": "Rename Method"
}
```

## MaRV Príklad

Zdroj: `data/processed/refactoring_marv/train.jsonl`

```json
{
  "instruction": "Vygeneruj refaktorovanú verziu nasledujúceho Java kódu podľa typu refaktoringu: Extract Method.",
  "input": "ProcessorSupplier<K, Change<V>> aggregateSupplier = new KTableAggregate<>(name, initializer, adder, subtractor); /* repartition setup inline */",
  "output": "ProcessorSupplier<K, Change<V>> aggregateSupplier = new KTableAggregate<>(name, initializer, adder, subtractor); return doAggregate(aggregateSupplier, aggValueSerde, AGGREGATE_NAME, name);",
  "domain": "refactoring",
  "source": "marv",
  "refactoring_type": "Extract Method"
}
```

## Combined Dataset

`data/processed/combined/` je balanced mix pre B1 shared fine-tuning:

- 4000 testing príkladov z Methods2Test,
- 4000 refactoring príkladov z ML4Refactoring.

MaRV sa do combined datasetu zatiaľ nepridáva.
