package validation.batches;

/** Pure integer batch calculation. No state or external dependencies. */
public final class BatchSizer {
    private BatchSizer() {}

    /** Returns the least number of capacity-sized groups holding items.
     * Zero items needs zero groups. Negative items or nonpositive capacity
     * cause IllegalArgumentException. All nonnegative int items are supported.
     */
    public static int groupsNeeded(int items, int capacity) {
        if (items < 0 || capacity <= 0) {
            throw new IllegalArgumentException("items >= 0 and capacity > 0 required");
        }
        return items / capacity + (items % capacity == 0 ? 0 : 1);
    }
}
