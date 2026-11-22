import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    @Test
    void preservesBothStatusBranches() {
        StatusLabel subject = new StatusLabel();
        assertEquals("ACTIVE", subject.label(true));
        assertEquals("INACTIVE", subject.label(false));
    }
}
