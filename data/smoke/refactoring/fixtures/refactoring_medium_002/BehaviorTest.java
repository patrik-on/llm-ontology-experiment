import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

final class BehaviorTest {
    private final UserGreeting subject = new UserGreeting();

    @Test
    void preservesRejectedInputs() {
        assertEquals("Unavailable", subject.greet(null, false));
        assertEquals("Unavailable", subject.greet("   ", false));
        assertEquals("Unavailable", subject.greet("Ada", true));
    }

    @Test
    void preservesTrimmedGreeting() {
        assertEquals("Hello, Ada", subject.greet("  Ada  ", false));
    }
}
