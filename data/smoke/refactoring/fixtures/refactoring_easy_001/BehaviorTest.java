import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final InvoiceTotal subject = new InvoiceTotal();

    @Test
    void preservesArithmeticAcrossRepresentativeValues() {
        assertEquals(30, subject.total(10, 3));
        assertEquals(0, subject.total(99, 0));
        assertEquals(-14, subject.total(-7, 2));
    }
}
