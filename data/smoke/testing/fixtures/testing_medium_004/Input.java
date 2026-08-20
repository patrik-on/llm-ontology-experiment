import java.util.Locale;

final class TextNormalizer {
    String normalize(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        return value.trim().toLowerCase(Locale.ROOT).replaceAll("\\s+", " ").trim();
    }
}
