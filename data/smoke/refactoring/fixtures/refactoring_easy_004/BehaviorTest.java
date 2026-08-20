import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesFormattingForBoundaryAndSignedValues() {
        DistanceFormatter subject = new DistanceFormatter();
        assertEquals("0 m", subject.format(0));
        assertEquals("42 m", subject.format(42));
        assertEquals("-3 m", subject.format(-3));
    }
}
