final class BookingValidator {
    boolean canBook(int requestedSeats, int availableSeats, boolean open) {
        if (open) {
            if (requestedSeats > 0) {
                if (requestedSeats <= availableSeats) {
                    return true;
                }
            }
        }
        return false;
    }
}
