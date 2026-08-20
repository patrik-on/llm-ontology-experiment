import java.util.ArrayList;
import java.util.List;

final class ScoreLedger {
    private final List<Integer> scores = new ArrayList<>();

    void addScore(int score) {
        if (score < 0 || score > 100) {
            throw new IllegalArgumentException("score outside 0..100");
        }
        scores.add(score);
    }

    List<Integer> scores() {
        return List.copyOf(scores);
    }

    double average() {
        return scores.stream().mapToInt(Integer::intValue).average().orElse(0.0);
    }
}
