import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesEveryEligibilityCondition() {
        BookingValidator subject = new BookingValidator();
        assertEquals(false, subject.canBook(1, 10, false));
        assertEquals(false, subject.canBook(0, 10, true));
        assertEquals(false, subject.canBook(-1, 10, true));
        assertEquals(false, subject.canBook(11, 10, true));
        assertEquals(true, subject.canBook(10, 10, true));
        assertEquals(true, subject.canBook(1, 10, true));
    }
}
