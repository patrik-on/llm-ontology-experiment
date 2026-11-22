final class ShippingFee {
    int calculate(int orderCents, boolean express, boolean member) {
        if (orderCents < 0) {
            throw new IllegalArgumentException("negative order total");
        }
        if (orderCents >= 5000) {
            return 0;
        }
        int fee = express ? 1200 : 500;
        if (member) {
            fee -= 200;
        }
        return Math.max(fee, 0);
    }
}
