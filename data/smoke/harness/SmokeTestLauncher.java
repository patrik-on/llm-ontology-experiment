import java.io.PrintWriter;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;

import static org.junit.platform.engine.discovery.DiscoverySelectors.selectClass;

public final class SmokeTestLauncher {
    private SmokeTestLauncher() {
    }

    public static void main(String[] args) {
        if (args.length != 1) {
            System.err.println("Usage: SmokeTestLauncher <test-class>");
            System.exit(2);
        }

        LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
                .selectors(selectClass(args[0]))
                .build();
        SummaryGeneratingListener listener = new SummaryGeneratingListener();
        Launcher launcher = LauncherFactory.create();
        launcher.registerTestExecutionListeners(listener);
        launcher.execute(request);
        listener.getSummary().printTo(new PrintWriter(System.out, true));
        listener.getSummary().getFailures().forEach(failure -> {
            System.err.println("FAILED: " + failure.getTestIdentifier().getDisplayName());
            failure.getException().printStackTrace(System.err);
        });

        long succeeded = listener.getSummary().getTestsSucceededCount();
        long failed = listener.getSummary().getTestsFailedCount();
        if (succeeded == 0 || failed > 0) {
            System.exit(1);
        }
    }
}
