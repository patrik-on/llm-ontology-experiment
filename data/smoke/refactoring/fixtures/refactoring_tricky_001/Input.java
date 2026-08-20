final class RiskClassifier {
    String classify(int failedLogins, boolean knownDevice, boolean admin) {
        if (admin) {
            if (failedLogins > 0) {
                return "REVIEW";
            }
            return "LOW";
        }
        if (!knownDevice) {
            if (failedLogins >= 3) {
                return "HIGH";
            }
            return "MEDIUM";
        }
        if (failedLogins >= 5) {
            return "HIGH";
        }
        return "LOW";
    }
}
