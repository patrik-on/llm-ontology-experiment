import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesCompleteTruthTable() {
        AccessPolicy subject = new AccessPolicy();
        assertEquals(false, subject.canAccess(false, false));
        assertEquals(false, subject.canAccess(false, true));
        assertEquals(true, subject.canAccess(true, false));
        assertEquals(false, subject.canAccess(true, true));
    }
}
