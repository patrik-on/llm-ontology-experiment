final class CartSummary {
    int totalWithTax(int[] itemCents, boolean reducedRate) {
        int total = 0;
        for (int item : itemCents) {
            total += item;
        }
        if (reducedRate) {
            int tax = total * 5 / 100;
            return total + tax;
        } else {
            int tax = total * 20 / 100;
            return total + tax;
        }
    }
}
