import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesPriorityAndDistanceBranches() {
        DeliveryEstimate subject = new DeliveryEstimate();
        assertEquals(2, subject.estimate(100, true));
        assertEquals(3, subject.estimate(101, true));
        assertEquals(4, subject.estimate(100, false));
        assertEquals(6, subject.estimate(101, false));
    }
}
