import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import org.refactoringminer.api.*;
import org.refactoringminer.rm1.GitHistoryRefactoringMinerImpl;
import gr.uom.java.xmi.diff.ExtractOperationRefactoring;
import gr.uom.java.xmi.diff.InlineOperationRefactoring;

/** Local file-content detection only. No GitHub access, generation or builds. */
public class RefactoringProbe {
    public static void main(String[] args) throws Exception {
        if (args.length == 1) {
            for (JsonElement item : JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray()) {
                JsonArray row = item.getAsJsonArray();
                String[] call = new String[4];
                for (int i = 0; i < 4; i++) call[i] = row.get(i).getAsString();
                try { main(call); }
                catch (Exception e) {
                    Files.writeString(Path.of(call[3]), new Gson().toJson(Map.of("error", e.toString())));
                }
            }
            return;
        }
        if (args.length != 4) throw new IllegalArgumentException("path before after output");
        List<Map<String, Object>> events = new ArrayList<>();
        boolean[] handled = {false};
        new GitHistoryRefactoringMinerImpl().detectAtFileContents(
            Map.of(args[0], Files.readString(Path.of(args[1]))),
            Map.of(args[0], Files.readString(Path.of(args[2]))), new RefactoringHandler() {
                @Override public void handle(String id, List<Refactoring> refs) {
                    handled[0] = true;
                    for (Refactoring ref : refs) {
                        Map<String, Object> event = new LinkedHashMap<>();
                        event.put("type", ref.getName());
                        event.put("description", ref.toString());
                        JsonObject detail = JsonParser.parseString(ref.toJSON()).getAsJsonObject();
                        event.put("left", detail.get("leftSideLocations"));
                        event.put("right", detail.get("rightSideLocations"));
                        if (ref instanceof ExtractOperationRefactoring e) {
                            event.put("target_class", e.getSourceOperationBeforeExtraction().getClassName());
                            event.put("target_method", e.getSourceOperationBeforeExtraction().getName());
                            event.put("target_start", e.getSourceOperationBeforeExtraction().getLocationInfo().getStartLine());
                            event.put("target_end", e.getSourceOperationBeforeExtraction().getLocationInfo().getEndLine());
                            event.put("path", e.getSourceOperationBeforeExtraction().getLocationInfo().getFilePath());
                        } else if (ref instanceof InlineOperationRefactoring e) {
                            event.put("target_class", e.getInlinedOperation().getClassName());
                            event.put("target_method", e.getInlinedOperation().getName());
                            event.put("target_start", e.getInlinedOperation().getLocationInfo().getStartLine());
                            event.put("target_end", e.getInlinedOperation().getLocationInfo().getEndLine());
                            event.put("path", e.getInlinedOperation().getLocationInfo().getFilePath());
                        }
                        events.add(event);
                    }
                }
                @Override public void handleException(String id, Exception e) { throw new RuntimeException(e); }
            });
        if (!handled[0]) throw new IllegalStateException("Detector never completed");
        Files.writeString(Path.of(args[3]), new Gson().toJson(Map.of("version", "3.0.10", "events", events)));
    }
}
