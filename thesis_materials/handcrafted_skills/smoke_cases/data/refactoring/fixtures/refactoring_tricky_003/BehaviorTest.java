import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

final class BehaviorTest {
    private final OrderTotal subject = new OrderTotal();

    @Test
    void preservesDiscountBeforeTaxAndRounding() {
        assertEquals(1200, subject.calculate(1000, false, "SK"));
        assertEquals(1080, subject.calculate(1000, true, "SK"));
        assertEquals(1098, subject.calculate(999, false, "CZ"));
        assertEquals(990, subject.calculate(999, true, "CZ"));
        assertEquals(1100, subject.calculate(1000, false, null));
    }

    @Test
    void preservesNegativeSubtotalValidation() {
        assertThrows(IllegalArgumentException.class, () -> subject.calculate(-1, false, "SK"));
    }
}
