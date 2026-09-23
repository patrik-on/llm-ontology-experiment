import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

final class BehaviorTest {
    private final PriceCalculator subject = new PriceCalculator();

    @Test
    void preservesDiscountAndIntegerRounding() {
        assertEquals(999, subject.finalPrice(999, 0));
        assertEquals(900, subject.finalPrice(1000, 10));
        assertEquals(670, subject.finalPrice(999, 33));
        assertEquals(0, subject.finalPrice(1200, 100));
    }

    @Test
    void preservesValidation() {
        assertThrows(IllegalArgumentException.class, () -> subject.finalPrice(-1, 10));
        assertThrows(IllegalArgumentException.class, () -> subject.finalPrice(100, -1));
        assertThrows(IllegalArgumentException.class, () -> subject.finalPrice(100, 101));
    }
}
