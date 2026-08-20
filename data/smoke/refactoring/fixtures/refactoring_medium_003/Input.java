final class DeliveryEstimate {
    int estimate(int distanceKm, boolean priority) {
        int days;
        if (priority) {
            days = distanceKm > 100 ? 2 : 1;
            days += 1;
        } else {
            days = distanceKm > 100 ? 5 : 3;
            days += 1;
        }
        return days;
    }
}
