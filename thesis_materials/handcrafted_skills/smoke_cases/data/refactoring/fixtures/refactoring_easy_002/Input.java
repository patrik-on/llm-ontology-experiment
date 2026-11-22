final class StatusLabel {
    String label(boolean active) {
        String unused = "legacy";
        if (active) {
            return "ACTIVE";
        }
        return "INACTIVE";
    }
}
