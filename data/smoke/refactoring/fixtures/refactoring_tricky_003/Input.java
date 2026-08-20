final class OrderTotal {
    int calculate(int subtotalCents, boolean premium, String country) {
        if (subtotalCents < 0) {
            throw new IllegalArgumentException("negative subtotal");
        }
        int total = subtotalCents;
        if (premium) {
            total = total - total * 10 / 100;
        }
        if ("SK".equals(country)) {
            total = total + total * 20 / 100;
        } else {
            total = total + total * 10 / 100;
        }
        return total;
    }
}
