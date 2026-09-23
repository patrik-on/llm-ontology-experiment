final class BoundedCounter {
    private int value;

    BoundedCounter(int initial) {
        if (initial < 0) {
            throw new IllegalArgumentException("negative initial value");
        }
        value = initial;
    }

    int increment(int limit) {
        if (limit < 0) {
            throw new IllegalArgumentException("negative limit");
        }
        if (value < limit) {
            value++;
        }
        return value;
    }

    int decrement() {
        if (value > 0) {
            value--;
        }
        return value;
    }

    int value() {
        return value;
    }
}
