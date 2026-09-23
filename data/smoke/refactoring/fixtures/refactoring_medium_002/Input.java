final class UserGreeting {
    String greet(String name, boolean suspended) {
        if (name != null) {
            if (!name.isBlank()) {
                if (!suspended) {
                    return "Hello, " + name.trim();
                }
            }
        }
        return "Unavailable";
    }
}
