# Príklady (surové dáta pre T4, T5, R4, R5)

## T4 – symbol z ontologického bloku, ktorý nie je v zdroji

Žiadny prípad – v žiadnej bunke nie je chýbajúci symbol, ktorý by bol v bloku a nie v zdroji. Namiesto toho prípady, kde onto rameno zlyhalo a jeho partner prešiel:

### onto_project / 5973732_200 (compile:cannot_find_symbol:class; qwen_base prešlo)

Blok:
```
<project-ontology>
Focal method: public static boolean equals(Object object1, Object object2) in ObjectUtils
Decision points (4): if object1 == object2, if object1 == null || object2 == null, if object1 instanceof Enum && object2 instanceof String, if object1 instanceof String && object2 instanceof Enum
Null checks: object1 == null, object2 == null
Calls: ((Enum<?>) object1).name, ((Enum<?>) object1).name().equals, ((Enum<?>) object2).name, object1.equals
Other public methods in supplied source: none
</project-ontology>
```
Chyba:
```
GeneratedBodyTests.java:18: error: cannot find symbol
assertEquals(true, ObjectUtils.equals(Enum.valueOf(MyEnum.class, "VALUE"), "VALUE"));
                                                   ^
  symbol:   class MyEnum
  location: class GeneratedBodyTests
```

### onto_project / 179549243_826 (compile:cannot_find_symbol:class; qwen_base prešlo)

Blok:
```
<project-ontology>
Focal method: public static void skipFully(InputStream in, long len) in IOUtils
Declared throws: IOException
throw EOFException at line 16; enclosing branches: loop amt > 0 > if ret == 0 > if b == -1; earlier return/throw at lines none
Decision points (3): loop amt > 0, if ret == 0, if b == -1
Boundary candidates: amt > 0 -> try amt = 0 / 1; ret == 0 -> try ret = -1 / 0 / 1; b == -1 -> try b = -2 / -1 / 0
Calls: in.read, in.skip
Other public methods in supplied source: none
</project-ontology>
```
Chyba:
```
GeneratedBodyTests.java:21: error: cannot find symbol
InputStream in = new ByteArrayInputStream(new byte[0]);
                     ^
  symbol:   class ByteArrayInputStream
  location: class GeneratedBodyTests
```

## T5 – symbol z retrieved kontextu

### rag_single / 206366_94 – symboly ['ByteBufferUtil']

Úryvok z retrieved:
```
rt java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import org.apache.accumulo.core.data.ByteSequence;
import org.apache.hadoop.io.Text;

public class ByteBufferUtil {

    public static byte[] toBytes(ByteBuffer buffer) {
        if (buffer == null)
            return null;
        return Arrays.copyOfRange(buffer.array(), buffer.position(), buffer
```
Chyba:
```
GeneratedBodyTests.java:20: error: cannot find symbol
assertEquals("Hello", ByteBufferUtil.toString(buffer));
                      ^
  symbol:   variable ByteBufferUtil
  location: class GeneratedBodyTests
GeneratedBodyTests.java:23: error: cannot find symbol
```

### rag_single / 177212349_369 – symboly ['getEmptyImplementationForCollectionInterface']

Úryvok z retrieved:
```
gregatedPayload> bundle = HttpAggregatedMultiIngestionHandler.createBundleList(badJson); }
Task: test generation

Methods2Test context level: src_fm

Production Java code:
public static Collection<?> getEmptyImplementationForCollectionInterface(final Class<?> collectionInterface) { Collection<?> collection = new ArrayList<>(); if (List.class.isAssignableFrom(collectionInterface)) { collection = ne
```
Chyba:
```
GeneratedBodyTests.java:22: error: cannot find symbol
List<String> input = Arrays.asList("apple", "banana"); List<String> result = ListUtils.copyOf(input); assertEquals(2, result.size()); assertTrue(result.contains("apple")); assertTrue(result.contains("banana"));
                     ^
  symbol:   variable Arrays
  location: class GeneratedBodyTests
GeneratedBodyTests.java:25: error: cannot find symbol
```

### rag_single / 29480568_231 – symboly ['CreateSnapshotRequestBinder']

Úryvok z retrieved:
```
tName>%s</snapshotName>", payload.name())) .append("</request>") .append("</ws:createSnapshot>"); return requestBuilder.toString(); }

Corresponding test code:
@Test public void testCreatePayload() { CreateSnapshotRequestBinder binder = new CreateSnapshotRequestBinder(); Snapshot.Request.CreatePayload payload = Snapshot.Request.creatingBuilder() .storageId("123-1233-1324") .name("snapshot-name") .
```
Chyba:
```
GeneratedBodyTests.java:18: error: cannot find symbol
assertEquals("<ws:createSnapshot><request><storageId>123-1233-1324</storageId></request></ws:createSnapshot>", new CreateSnapshotRequestBinder().createPayload(Snapshot.Request.creatingBuilder().storageId("123-1233-1324").name("snapshot-name").description("describing-the-snapshot").build()));
                                                                                                                   ^
  symbol:   class CreateSnapshotRequestBinder
  location: class GeneratedBodyTests
GeneratedBodyTests.java:18: error: package Snapshot does not exist
```

### rag_single / 30952948_970 – symboly ['InvalidDataException']

Úryvok z retrieved:
```
List<AggregatedPayload> createBundleList(String json) { Gson gson = new Gson(); JsonParser parser = new JsonParser(); JsonElement element = parser.parse(json); if (!element.isJsonArray()) { throw new InvalidDataException("Invalid request body"); } JsonArray jArray = element.getAsJsonArray(); ArrayList<AggregatedPayload> bundleList = new ArrayList<AggregatedPayload>(); for(JsonElement obj : jArray 
```
Chyba:
```
GeneratedBodyTests.java:24: error: cannot find symbol
assertThrows(InvalidDataException.class, () -> StringUtil.parseCSV(null));
             ^
  symbol:   class InvalidDataException
  location: class GeneratedBodyTests
1 error
```

## R4 – rag_single, nové riadky z kontextu

### ml4refactoring-10b2d8f4d7c8f1c364b35c45 (Rename Class, status structural_pass) – 3/5 nových riadkov z kontextu

```
public class CompositeDestinationFilter extends DestinationFilter {
public CompositeDestinationFilter(Destination next, Collection forwardDestinations, boolean forwardOnly, boolean copyMessage) {
context.setMutable(true);
```

### ml4refactoring-01c0b9f988bc3e869b93fbdd (Rename Parameter, status structural_pass) – 1/6 nových riadkov z kontextu

```
import java.net.URI;
```

### ml4refactoring-08bccb1cea13603171e25c95 (Parameterize Variable, status checks_failed) – 1/24 nových riadkov z kontextu

```
@Override
```

## R4 – rag_single no_op: diff vstup→výstup bez prázdnych riadkov

### marv-26dbe5d1e6c7d2b81fc89f23 (Rename Method; cieľ: Rename Method	public apply(infos PCollection<GameActionInfo>) : PCollection<KV<String,Integer>> renamed to public expand(infos PCollection<GameActionInfo>) : PCollection<KV<String,Integer>> in class o)

prompt 10267 tok; zmenených neprázdnych riadkov: 17
```diff
--- before(bez prázdnych)
+++ rag_single
@@ -1,17 +0,0 @@
-/*
- * Licensed to the Apache Software Foundation (ASF) under one
- * or more contributor license agreements.  See the NOTICE file
- * distributed with this work for additional information
- * regarding copyright ownership.  The ASF licenses this file
- * to you under the Apache License, Version 2.0 (the
- * "License"); you may not use this file except in compliance
- * with the License.  You may obtain a copy of the License at
- *
- *     http://www.apache.org/licenses/LICENSE-2.0
- *
- * Unless required by applicable law or agreed to in writing, software
- * distributed under the License is distributed on an "AS IS" BASIS,
```

### marv-552dc590d098dd11018a533f (Remove Parameter; cieľ: Remove Parameter	key : DataKey in method public serializeTo(key DataKey, sourceTable DataSourceTable, output OutputStream) : int from class com.google.devtools.build.android.DataValueFile)

prompt 6524 tok; zmenených neprázdnych riadkov: 1
```diff
--- before(bez prázdnych)
+++ rag_single
@@ -2 +1,0 @@
-//
```

### marv-83018b0cf6ae0eebc3982566 (Extract Method; cieľ: Extract Method	public renderPng(out OutputStream, width int, height int, hideLegend boolean, hideGrid boolean, hideTitle boolean, showEvents boolean, periodCount int, end int, showCredit boolean, lsnr)

prompt 8358 tok; zmenených neprázdnych riadkov: 0
```diff

```

## R5 – FT výstup na SWE (unified diff vstup→výstup, prvých 40 riadkov)

### ft_refactoring / 12dbeafe93f7 (Extract Method, checks_failed)

```diff
--- before
+++ ft_refactoring
@@ -20,4 +20,6 @@
 import java.io.IOException;
-import java.io.UncheckedIOException;
+
 import java.util.function.Supplier;
+
+import org.apache.commons.io.UncheckedIOException;
 
@@ -39,3 +41,3 @@
     default Supplier<T> asSupplier() {
-        return () -> Uncheck.get(this);
+        return () -> UncheckedIOException.of(this);
     }
```

### ft_refactoring / 3ac63df5d566 (Extract Method, no_op)

```diff
--- before
+++ ft_refactoring
@@ -20,6 +20,11 @@
 import java.io.IOException;
+
 import java.nio.file.CopyOption;
+
 import java.nio.file.FileVisitResult;
+
 import java.nio.file.Files;
+
 import java.nio.file.Path;
+
 import java.nio.file.attribute.BasicFileAttributes;
@@ -38,3 +43,5 @@
     private final CopyOption[] copyOptions;
+
     private final Path sourceDirectory;
+
     private final Path targetDirectory;
```

### ft_refactoring / 4d63091bdc21 (Extract Method, no_op)

```diff

```

