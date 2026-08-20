import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final RiskClassifier subject = new RiskClassifier();

    @Test
    void preservesAdminOverride() {
        assertEquals("LOW", subject.classify(0, false, true));
        assertEquals("REVIEW", subject.classify(1, true, true));
    }

    @Test
    void preservesDeviceSpecificThresholds() {
        assertEquals("MEDIUM", subject.classify(2, false, false));
        assertEquals("HIGH", subject.classify(3, false, false));
        assertEquals("LOW", subject.classify(4, true, false));
        assertEquals("HIGH", subject.classify(5, true, false));
        assertEquals("MEDIUM", subject.classify(-1, false, false));
    }
}
