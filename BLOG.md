# The Brain Behind the Scroll

*Building a virality predictor on top of Meta's TRIBE v2, and learning where the science ends and the guessing begins.*

---

There's a half-second that decides everything.

You're scrolling. A video starts. Somewhere in that first beat, before you've consciously decided anything, your brain has already begun to vote. A little surge here, a flicker of recognition there, a quiet *meh* that makes your thumb twitch upward. We've all felt it from the inside. What I never expected was to be able to watch it from the outside, on a video that no human had reacted to yet.

This is the story of how I tried to do that, what I actually managed to build, and everything I was careful not to claim.

## The model that pulled me in

In 2026, Meta Research published something I found hard to stop thinking about: **[TRIBE v2](https://ai.meta.com/research/publications/a-foundation-model-of-vision-audition-and-language-for-in-silico-neuroscience/)**, a foundation model that predicts how a human brain responds to almost any sight or sound.

Not a metaphorical brain. The real thing: BOLD fMRI activation, the same signal a person generates lying inside a scanner while they watch a movie. TRIBE v2 was trained on a unified dataset of over 1,000 hours of fMRI across 720 subjects, and its predecessor had already won the 2025 Algonauts brain-encoding challenge. It's trimodal. Three pretrained towers (V-JEPA2 for video, Wav2Vec-BERT for audio, and Llama-3.2-3B for the transcribed language) feed a unified Transformer that maps everything onto the cortical surface. Give it a clip and it returns a per-vertex activation map on the `fsaverage5` cortical mesh (~20,484 vertices), frame by frame, at roughly 2 Hz.

The phrase the researchers use for what this unlocks is the one that hooked me: **in-silico neuroscience**. You can run a brain experiment without a brain in the room. Want to know how the visual cortex responds to a stimulus nobody has ever scanned? Don't book scanner time. Ask the model.

One detail stuck with me more than the rest. Nobody told TRIBE what the brain's functional regions were. Train it well enough and its internal representations organize themselves into the networks neuroscientists already named by hand: auditory, language, motion, the default-mode network, visual. The map drew itself.

I read all of that, and one slightly reckless question wouldn't leave me alone.

## The leap: from what the brain does to what the crowd will do

What I kept staring at was the bridge between two ideas.

Back in 2020, Genevsky, Yoon, and Knutson published a study in *PNAS* with a title that reads like science fiction: **["Brain activity forecasts video engagement in an internet attention market."](https://pmc.ncbi.nlm.nih.gov/articles/PMC7104008/)** They scanned a small group of people watching videos and found that activity in specific regions, increased **nucleus accumbens** (reward) and decreased **anterior insula** (a salience and aversion signal) at the *onset* of a video, forecast how the broader internet would later engage with it. The handful of brains in the scanner predicted the behavior of millions who were never measured. Neuroforecasting, they called it. A few people's neurons outvoting their own stated opinions.

Lay the two ideas side by side:

- TRIBE v2 can **simulate** a brain's response to any video.
- A real brain's response can, in narrow conditions, **forecast** how a crowd will engage.

Connect them and you get a thought experiment that's hard to put down. Could you ask a simulated brain whether a video will land before a single human ever sees it? Upload your cut, run it through the model, and get a number back.

This is a leap, not a proof. But it was the leap that made me open my editor.

## What I actually built

The project is called **Tribe Virality**, and the front door asks a blunt question: *"How viral will your video be?"* You drop in a clip, and a few moments later you're watching a 3D brain light up in time with your footage, with a virality score ticking underneath. There were really three pieces to build.

**First, make the brain runnable.** TRIBE is big and far from plug-and-play, so I hosted it as a service you can send a video to and get a brain response back, no setup required. It watches your clip, listens to the audio, reads the transcribed speech, and predicts activity across the surface of the cortex, frame by frame. That prediction is the raw material for everything else.

**Second, turn that brain activity into a score.** This is the heart of it, and the part where I have to be most careful. TRIBE gives you raw cortical activation, shape `(T, 20484)`: one value per timestep for every vertex on the cortical mesh. It does **not** give you a "virality score." That layer is mine, and it's a heuristic, not a discovery. The pipeline:

1. Using the **Destrieux cortical atlas**, I group the cortex's vertices into five cognitive constructs.
2. For each construct, I take the mean activation across its vertices.
3. I convert that to a 0-100 score with a *signed* z-score against an empirical baseline, squashed through a sigmoid: `sigmoid(sign · (x − μ) / σ) · 100`.
4. The five sub-scores combine, by weight, into one headline number.

The five constructs, with the honest admission that these are literature-informed proxies, not validated readouts:

| Sub-score | Weight | Cortical proxy |
| --- | --- | --- |
| Reward | 30% | Orbitofrontal cortex, ventromedial PFC |
| Emotion | 25% | Anterior insula, anterior cingulate *(sign-inverted)* |
| Attention | 20% | Visual & auditory cortex, intraparietal sulcus |
| Social Relevance | 15% | Medial PFC, TPJ, precuneus |
| Novelty | 10% | Parahippocampal cortex, posterior cingulate |

The sign-flip on **Emotion** is the one place the math directly inherits the neuroforecasting result. Per Genevsky & Knutson, *higher* anterior-insula activity forecasts *lower* engagement, so in my scoring, more of it pushes the score down. The whole transform is deterministic: same file in, same number out.

**Third, make it something you can play with.** The result is a page where your video sits next to a 3D brain that re-colors itself frame by frame as the clip plays, a timeline showing how the five sub-scores rise and fall across its length, and a history panel so you can re-cut your edit, run it again, and watch the score move. No account, nothing stored, no tracking. It turns a research model into a toy you can poke at.

## The most important part of the project is a disclaimer

If you take one thing from this post, take this: the file I'm proudest of isn't a clever algorithm. It's [`METHODOLOGY.md`](./cog/METHODOLOGY.md), the document that says in plain language exactly where the science runs out.

It would have been easy to ship the number and let the demo do the talking. Instead I wrote down everything that *isn't* validated, because a virality score that hides its own uncertainty isn't a tool. It's a magic trick. The honest limitations:

- **There is no engagement-labelled validation.** I have no corpus of videos with real view counts to check the mapping against. So the score is an *experimental relative heuristic*, useful for comparing your own edits to each other, not a calibrated probability of going viral.
- **The baseline is small and arbitrary.** The μ and σ I z-score against come from a few dozen generic clips with no engagement labels. That calibrates "typical of those clips," not "typical of things that go viral."
- **The best signal is missing.** The strongest neuroforecasting predictor, the **nucleus accumbens**, is subcortical, and the packaged model only exposes cortex. My "reward" sub-score is an orbitofrontal/vmPFC proxy for a signal I can't actually see.
- **Reverse inference is a known fallacy.** TRIBE predicts BOLD activation, not "reward" or "emotion." Naming a region's activity after a feeling is an interpretive leap, and I labeled it as one.
- **Even the vertex ordering is an assumption** that still needs to be verified against the model's true output layout.

TRIBE's own authors set the tone. They're explicit that the model *"treats the brain as a passive observer of naturalistic stimuli; it does not yet model the brain as an active agent producing behavior."* Group-level encoding accuracy sits around R ≈ 0.4. It's a remarkable instrument and an honest one, and I tried to inherit that honesty rather than launder it into false confidence.

So is the score "real"? It's real math on a real brain prediction, built on a real neuroforecasting finding. It's also, end to end, an unvalidated heuristic. Both of those sentences are true, and a responsible tool says both out loud.

## Where this field goes next

Standing back from my own small project, the bigger picture is the part I find genuinely exciting.

**In-silico neuroscience becomes a real instrument.** The real story here isn't that AI predicts virality. It's that we now have a usable simulator of the brain's sensory response. Scanner time is scarce, expensive, and slow. A model you can query a thousand times before lunch changes which experiments are even thinkable. Screen stimuli before scanning. Probe languages and images no one has the budget to collect. It's a new kind of microscope, and we're still learning to focus it.

**Neuroforecasting grows up, or it doesn't.** For the content-prediction dream to move from "tempting" to "trustworthy," a few things have to happen: a real engagement-labelled corpus to validate against, access to subcortical structure (the nucleus accumbens again), and per-subject models instead of one average brain. My project is, in a sense, a placeholder waiting for that validation to exist. The scaffolding is built; the ground truth is the missing brick.

**The dual edge is worth saying out loud.** A tool that optimizes content for the brain's reward circuitry is, from another angle, a persuasion engine. The same pipeline that helps an educator make a lesson land could help an attention market get better at capturing attention people never chose to give. I built this as an open, non-commercial research artifact with its limitations stapled to the front, partly because I think that's the only responsible posture while the science is this young. The more capable these models get, the more that posture matters.

The hopeful version is the one I'd bet on. Brain encoders like TRIBE eventually do more for medicine and accessibility than for marketing: faster paths to understanding neurological disease, better models of attention, interfaces that adapt to how a particular mind actually processes the world.

## The half-second, revisited

I started with that half-second where your brain quietly decides whether to keep watching. I can't claim I've captured it. What I can say is that I built something that lets you watch a model's best guess at it: a brain on a screen, lighting up in time with your footage, with the appropriate humility printed in the margins.

The whole thing is open source under CC-BY-NC-4.0. The model packaging, the scoring math, and the long list of things it can't yet prove are all there to read, poke at, and improve. With a Replicate account and a little curiosity, you can run the real Meta brain model against your own video tonight.

Bring a clip. Bring some skepticism. Watch the brain light up, and then go read the disclaimer.

---

### References & further reading

- **TRIBE v2.** *A foundation model of vision, audition and language for in-silico neuroscience.* [Meta AI Research](https://ai.meta.com/research/publications/a-foundation-model-of-vision-audition-and-language-for-in-silico-neuroscience/) · [arXiv:2605.04326](https://arxiv.org/abs/2605.04326) · [facebook/tribev2 on HuggingFace](https://huggingface.co/facebook/tribev2)
- **Genevsky, Yoon & Knutson (2020).** *Brain activity forecasts video engagement in an internet attention market,* PNAS. [PMC7104008](https://pmc.ncbi.nlm.nih.gov/articles/PMC7104008/)
- **Destrieux et al. (2010).** *Automatic parcellation of human cortical gyri and sulci,* NeuroImage (the `aparc.a2009s` atlas).
- **This project.** Methodology, grounding, and limitations in [`cog/METHODOLOGY.md`](./cog/METHODOLOGY.md); architecture in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md); the scoring math in [`cog/README.md`](./cog/README.md#scoring).
