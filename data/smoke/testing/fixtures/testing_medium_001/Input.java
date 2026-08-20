final class Divider {
    int divide(int numerator, int denominator) {
        if (denominator == 0) {
            throw new ArithmeticException("division by zero");
        }
        return numerator / denominator;
    }
}
