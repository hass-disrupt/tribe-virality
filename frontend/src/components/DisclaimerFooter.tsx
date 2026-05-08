export function DisclaimerFooter() {
  return (
    <footer className="border-t border-border-subtle mt-auto py-5 px-6">
      <p className="max-w-6xl mx-auto text-xs text-ink-dim leading-relaxed text-center">
        Research-grade approximation. Scores are computed from cortical proxies of reward,
        emotion, attention, novelty, and social-cognition networks using Meta's{" "}
        <a
          href="https://ai.meta.com/blog/tribe-v2-brain-predictive-foundation-model/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent hover:underline"
        >
          TRIBE v2
        </a>{" "}
        model (CC-BY-NC-4.0). Not clinical. Not a guarantee of actual performance.
      </p>
    </footer>
  );
}
