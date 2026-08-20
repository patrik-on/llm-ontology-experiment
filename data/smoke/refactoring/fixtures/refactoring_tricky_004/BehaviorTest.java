import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final NotificationPreference subject = new NotificationPreference();

    @Test
    void preservesGlobalGuards() {
        assertEquals(false, subject.shouldNotify(false, false, 10, true));
        assertEquals(false, subject.shouldNotify(true, true, 10, false));
    }

    @Test
    void preservesOwnerAndPriorityThresholds() {
        assertEquals(false, subject.shouldNotify(true, false, 7, false));
        assertEquals(true, subject.shouldNotify(true, false, 8, false));
        assertEquals(false, subject.shouldNotify(true, false, 4, true));
        assertEquals(true, subject.shouldNotify(true, false, 5, true));
        assertEquals(true, subject.shouldNotify(true, true, 5, true));
    }
}
