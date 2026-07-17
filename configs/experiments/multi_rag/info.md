# configs/experiments/multi_rag

Konfigurácie pre viac špecializovaných retrieval zdrojov. Šablóna počíta so
samostatnými kolekciami Methods2Test, ML4Refactoring a MaRV a s RRF fusion.

Experiment je zatiaľ vypnutý. Pri kontrolovanom porovnaní musí multi-RAG
používať rovnaký celkový train-only korpus ako jednotný RAG; rozdiel má byť v
organizácii, routingu a fusion, nie v množstve dostupných dát.
