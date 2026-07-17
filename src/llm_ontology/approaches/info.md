# src/llm_ontology/approaches

Generation approaches určujú, ako sa pred inferenciou zostaví prompt a kontext.

- `direct/`: čistý prompt bez retrieval kontextov,
- `rag/`: jeden zoradený zoznam retrieval kontextov,
- `multi_rag/`: kontexty zoskupené podľa viacerých zdrojov,
- `contracts.py`: `PromptRequest`, `RetrievedContext`, `PreparedPrompt`,
- `registry.py`: normalizovaný výber approach,
- `context_prompt.py`: bezpečné a auditovateľné renderovanie kontextov.

RAG approach vyžaduje aspoň jeden kontext a multi-RAG takisto nemôže potichu
spadnúť na direct prompt. Retrieval obsah je označený ako nedôveryhodný
referenčný materiál. Samotné vyhľadávanie patrí do `llm_ontology.retrieval`.
