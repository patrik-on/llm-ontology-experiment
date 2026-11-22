final class AccessPolicy {
    boolean canAccess(boolean enabled, boolean locked) {
        if (enabled == true && locked == false) {
            return true;
        } else {
            return false;
        }
    }
}
