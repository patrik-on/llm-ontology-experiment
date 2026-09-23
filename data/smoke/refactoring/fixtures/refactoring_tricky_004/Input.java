final class NotificationPreference {
    boolean shouldNotify(boolean enabled, boolean muted, int priority, boolean owner) {
        if (!enabled) {
            return false;
        }
        if (muted && !owner) {
            return false;
        }
        if (priority >= 8) {
            return true;
        }
        if (owner && priority >= 5) {
            return true;
        }
        return false;
    }
}
