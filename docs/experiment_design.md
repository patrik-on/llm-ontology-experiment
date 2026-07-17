# Experiment Design

Projekt oddeľuje tri osi experimentu:

- model variant: base model alebo model s LoRA adaptérom,
- generation approach: direct, RAG alebo multi-RAG,
- task: JUnit test generation alebo Java refactoring.

## Primary RAG comparison

Prvé kontrolované porovnanie používa rovnaký base model a rovnaké testovacie
príklady:

1. `direct`: kvalitný prompt bez retrieval kontextu,
2. `rag`: jeden zjednotený train-only index,
3. `multi_rag`: rovnaký korpus rozdelený medzi špecializované retrievery a fusion.

RAG a multi-RAG musia používať rovnaký celkový korpus. Rozdiel má byť v
organizácii retrievalu, nie v množstve dostupných informácií. Val split slúži
na ladenie a test split sa nesmie indexovať.

## Fine-tuning comparison

Existujúce modely zostávajú samostatnou experimentálnou osou:

- B1 shared fine-tuning,
- B2-R refactoring fine-tuning,
- B2-T testing fine-tuning.

Po dokončení základného RAG porovnania možno vytvoriť kombinácie, napríklad
`b2_testing_v2 × rag × testing`, bez duplikácie dátovej alebo evaluation pipeline.
