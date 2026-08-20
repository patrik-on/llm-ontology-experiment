final class RangeValidator {
    boolean isWithin(int value, int minimum, int maximum) {
        if (minimum > maximum) {
            throw new IllegalArgumentException("minimum exceeds maximum");
        }
        return value >= minimum && value <= maximum;
    }
}
