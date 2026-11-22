final class WindowSlice {
    String slice(String value, int start, int length) {
        if (value == null) {
            throw new IllegalArgumentException("value is null");
        }
        if (start < 0 || length < 0 || start > value.length() - length) {
            throw new IndexOutOfBoundsException("invalid window");
        }
        return value.substring(start, start + length);
    }
}
