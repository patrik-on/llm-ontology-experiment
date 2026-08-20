# configs/experiments/multi_rag

Konfigurácie pre viac špecializovaných retrieval zdrojov. Aktuálny baseline
číta `testing_db` a `refactoring_db` paralelne a používa RRF s `k=60`.

Šablóna je zámerne vypnutá proti náhodnému batch behu, ale runner je
implementovaný. Pri kontrolovanom porovnaní musí MultiRAG
používať rovnaký celkový train-only korpus ako jednotný RAG; rozdiel má byť v
organizácii a fusion, nie v množstve dostupných dát. Baseline nemá router.
