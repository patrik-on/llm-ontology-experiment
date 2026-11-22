import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

final class BehaviorTest {
    private final CartSummary subject = new CartSummary();

    @Test
    void preservesSummationRatesAndIntegerRounding() {
        assertEquals(0, subject.totalWithTax(new int[] {}, true));
        assertEquals(103, subject.totalWithTax(new int[] {33, 66}, true));
        assertEquals(118, subject.totalWithTax(new int[] {33, 66}, false));
        assertEquals(360, subject.totalWithTax(new int[] {100, 200}, false));
    }

    @Test
    void preservesNullFailure() {
        assertThrows(NullPointerException.class, () -> subject.totalWithTax(null, true));
    }
}
