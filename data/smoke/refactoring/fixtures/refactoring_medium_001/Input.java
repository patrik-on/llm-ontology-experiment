final class PriceCalculator {
    int finalPrice(int baseCents, int discountPercent) {
        if (baseCents < 0 || discountPercent < 0 || discountPercent > 100) {
            throw new IllegalArgumentException("invalid price or discount");
        }
        int discount = baseCents * discountPercent / 100;
        return baseCents - discount;
    }
}
