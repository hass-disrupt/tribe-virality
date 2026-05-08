# TRIBE Virality — Replicate Redesign Spec

**Date:** 2026-05-08
**Status:** Draft, awaiting user review
**Supersedes:** `2026-05-07-tribe-virality-webapp-design.md` (the prior local/hosted-pluggable backend design)

## 1. Why this redesign

The original design assumed a Python backend that could swap between mock, local-MPS, and hosted inference. The local-MPS path has not stabilized on Apple Silicon (toolchain compatibility blockers, see the prior `docs/mps-status.md`), and running TRIBE v2 locally is not practical for end users either. The product needs a real-inference path that works for any user without GPU hardware.

A public Replicate model has been created at `prakhar-bhartiya/meta-tribev2-social-media-content-signal` to host the TRIBE v2 inference. This spec defines a redesign in which:

1. All inference happens on Replicate.
2. The application becomes browser-only — no Python backend on the deployment host.
3. The user supplies their own Replicate API token, which never crosses any server we operate.
4. Session state is held in browser memory only (stateless, research-tool ethos).

Hosting plan: a Hostinger VM serving the static frontend bundle via nginx. No application server.

## 2. Goals & non-goals

### Goals

- Run real TRIBE v2 inference on every prediction with no developer-side GPU.
- Eliminate the FastAPI backend entirely from the deployment surface.
- Keep the user's Replicate API token off any server we control.
- Preserve the existing visual experience: interactive 3D brain (`HeadViewer3D`), frame strip (`BrainFrameStrip`), score row, timeline chart, attempts/comparison.
- Provide an honest, well-paced processing UX that handles Replicate cold starts (~30–90s) without feeling broken.
- Make the legal disclaimer the literal first thing a user sees, acknowledged before anything else.

### Non-goals

- User accounts, authentication, server-side session management.
- Server-side persistence of any kind. No SQLite, no filesystem state, no logs that contain user content or tokens.
- Mobile-first layout (desktop, tablet-tolerant only).
- Multi-tenant deployment, billing, or quota enforcement (the user pays Replicate directly).
- Reimplementing the scoring pipeline or 3D rendering twice in different languages.
- Continuing the local-MPS inference path. It is abandoned by this spec.

## 3. Architecture

### 3.1 Diagram

```
┌────────────────────────────────────────┐
│ Browser (single-page React app)        │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ In-memory state (React context)  │  │
│  │  • apiKey: string | null         │  │
│  │  • attempts: Attempt[]           │  │
│  │  • currentJobId: string | null   │  │
│  └──────────────────────────────────┘  │
│        │                               │
│        ▼                               │
│  ┌──────────────────────────────────┐  │
│  │ ReplicateClient (lib/replicate.ts)│ │
│  │  • uploadFile(blob) → fileUrl    │  │
│  │  • createPrediction(input) → id  │  │
│  │  • pollPrediction(id) → status   │  │
│  │  • cancelPrediction(id)          │  │
│  └──────────────────────────────────┘  │
└──────────────┬─────────────────────────┘
               │  HTTPS  (Authorization: Bearer <user key>)
               ▼
┌────────────────────────────────────────┐
│ api.replicate.com                      │
│   POST /v1/files            ← upload   │
│   POST /v1/predictions      ← run      │
│   GET  /v1/predictions/{id} ← poll     │
│   POST /v1/predictions/{id}/cancel     │
│   GET  /v1/account          ← validate │
└──────────────┬─────────────────────────┘
               │ runs the model image on a GPU worker
               ▼
┌────────────────────────────────────────┐
│ Replicate model: prakhar-bhartiya/     │
│ meta-tribev2-social-media-content-     │
│ signal  (cog package)                  │
│                                        │
│  predict.py:                           │
│    1. download video from URL          │
│    2. tribev2.predict() → preds (T,V)  │
│    3. score(preds) → scores + timeline │
│    4. return Output(...)               │
└────────────────────────────────────────┘
```

### 3.2 Key invariant

Every byte that crosses to a system we operate (Hostinger nginx) is static HTML, JS, or CSS. The user's API token, video bytes, and prediction outputs flow only between the browser and `api.replicate.com`. We hold no secrets, no user data, and no logs.

### 3.3 Replicate model output contract

The cog `Predictor` returns a typed object. Replicate serializes it as JSON; file outputs become URLs.

```python
class Output(BaseModel):
    headline_score: int                # 0–100
    sub_scores: dict[str, int]         # keys: reward, emotion, attention, novelty, social_relevance
    timeline: list[dict[str, float]]   # [{t, reward, emotion, attention, novelty, social_relevance}, ...]
    video_duration_s: float
    frame_count: int                   # = len(timeline)
    model_version: str                 # tribev2 commit/checkpoint identifier
    scoring_version: str               # bumps when weights or baseline change
```

**No `brain_video` file output.** All brain visualization happens client-side via `HeadViewer3D` (interactive Three.js scene, already present) and canvas snapshots for `BrainFrameStrip`. The Replicate model only returns numeric data.

### 3.4 What changes vs the prior design

- The pluggable inference protocol (`mock` / `local` / `hosted` backends) is gone. Only Replicate.
- The capability banner (green/yellow/red tier) is gone. The only "capability" is whether the user has provided a working API token, enforced by the `ApiKeyGate`.
- PyVista brain rendering is gone from the deployment surface. Browser-side `HeadViewer3D` is the canonical brain visualization; `BrainFrameStrip` sources its frames from offscreen WebGL captures of the same scene.
- Server-side per-second video thumbnails are gone. The browser draws thumbnails from the `<video>` element via canvas.
- Session identity (`X-Session-Id`) is gone. There are no sessions on any server.

## 4. Frontend state model

### 4.1 In-memory context

```ts
// lib/AppState.tsx
type Attempt = {
  attemptId: string;                    // local UUID, distinct from Replicate prediction id
  predictionId: string;                 // Replicate id (r8_...)
  label: string;                        // "v1", "v2", or user-named
  videoBlobUrl: string;                 // URL.createObjectURL(file) — kept until tab close
  videoDurationS: number;
  uploadedAt: string;                   // ISO timestamp
  status: "queued" | "processing" | "done" | "error";
  headlineScore: number | null;
  subScores: SubScores | null;
  timeline: TimelinePoint[] | null;
  frameCount: number;
  modelVersion: string | null;
  scoringVersion: string | null;
  brainFrames: string[] | null;          // data URLs, lazily filled on Results mount
  errorMessage: string | null;
};

type AppState = {
  apiKey: string | null;
  apiKeyAccount: { username: string; type: string } | null;
  attempts: Attempt[];                   // newest first
  currentJobId: string | null;
};
```

Single `<AppStateProvider>` wraps the router. Three hooks: `useApiKey()`, `useAttempts()`, `useCurrentJob()`. The Replicate client is constructed lazily and recreated when `apiKey` changes.

**Persistence rule:** the only thing written to disk by the app is the legal disclaimer acknowledgment flag (§6.3). Everything else lives in React state and is zeroed on tab close or full refresh.

### 4.2 Attempts and comparison

- `attempts[]` is in-memory only.
- Newest first.
- `addAttempt()` prepends; `removeAttempt()` filters by id.
- Comparison mode (selecting ≥2 attempts) shows side-by-side score rows and overlaid timelines (solid + dashed); no server state, just UI.
- Refreshing the tab clears all attempts. This matches the API-key lifetime (refresh clears the key too).

## 5. API key UX

### 5.1 Lifetime

In-memory only. No `localStorage`, no `sessionStorage`. Lost on refresh, tab close, or explicit "forget key".

### 5.2 ApiKeyGate

Full-screen route guard. When `apiKey === null`, this renders instead of the page content. Cannot be bypassed.

Layout (textual mockup):

```
┌───────────────────────────────────────────────────────────────────┐
│  Tribe Virality                                                   │
│                                                                   │
│  This is a research tool. To run a prediction we need your        │
│  Replicate API token — you bring your own credits.                │
│                                                                   │
│  ┌─ How this works ─────────────────────────────────────────────┐ │
│  │ 1. Create a free Replicate account at replicate.com          │ │
│  │ 2. Add billing credits (predictions cost ~$0.05–0.20 each)   │ │
│  │ 3. Create an API token at replicate.com/account/api-tokens   │ │
│  │ 4. Paste it below                                            │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Replicate API token                                              │
│  ┌──────────────────────────────────────────────────┐  [Continue] │
│  │ r8_·····················              👁          │             │
│  └──────────────────────────────────────────────────┘             │
│                                                                   │
│  🔒 Stored in memory only. Cleared when you refresh or close      │
│     this tab. Never sent to any server we operate.                │
└───────────────────────────────────────────────────────────────────┘
```

### 5.3 Validation

On Continue:
1. Show inline spinner ("Verifying token…").
2. `GET https://api.replicate.com/v1/account` with `Authorization: Bearer <token>`.
3. On 200: cache `{username, type}` into context, set `apiKey`, dismiss the gate.
4. On 401: inline error "That token didn't work — double-check you copied the whole `r8_…` string."
5. On network error / 5xx: "Couldn't reach Replicate. Try again."

This is the only Replicate request that runs before an upload, and it does not consume credits.

### 5.4 Persistent header chip

Once a key is loaded, a chip appears top-right on every page:

```
[ ●  <username>  · forget key ]
```

- Click "forget key" → clears `apiKey`, `apiKeyAccount`, `attempts`, and `currentJobId`. Routes back to `ApiKeyGate`.
- Acts as a constant reminder that a key is loaded.

### 5.5 Security properties

- Token never written to disk.
- Token only ever sent to `api.replicate.com`. A single `replicateFetch()` helper hardcodes the host; no other code may originate cross-origin requests with the `Authorization` header.
- Token not visible in serialized DOM (held in React state, not in form attributes).
- Token scrubbed from any thrown Error message before it bubbles to the UI or `console.error` (the helper wraps fetch and rewrites error strings).
- No telemetry, no analytics, no logs to any server we operate.

## 6. Disclaimer flow

### 6.1 First-open funnel

```
   ┌────────────┐    ┌────────────┐    ┌────────────────┐
   │ Disclaimer │───▶│ ApiKeyGate │───▶│ Main app (any  │
   │  (§6.2)    │    │  (§5.2)    │    │  page)         │
   └────────────┘    └────────────┘    └────────────────┘
       ▲ shown if no ack flag      ▲ shown if apiKey===null
```

Both gates are full-page route guards in the React Router layout.

### 6.2 Disclaimer screen content

Full-viewport, scrollable, near-black background, centered card (max 720px). Required checkbox + button at the end. No close button, no "skip", no escape hatch.

Content sections:
- **About this tool.** What it is, that it uses Meta TRIBE v2 on Replicate, and that the user supplies their own token and credits.
- **About TRIBE v2.** `facebook/tribev2`, CC-BY-NC-4.0 license, non-commercial use only.
- **Accuracy & limitations.** Research-grade approximation; cortical proxies only (no subcortical structures); virality is a heuristic with no guaranteed correlation to real-world performance; not medical, diagnostic, or psychological advice.
- **Your data.** Video uploads go directly browser → Replicate, never through any server the developer operates. API token in browser memory only. No accounts, no telemetry, no analytics.
- **Costs.** Each prediction is billed by Replicate to the user's account; ~$0.05–0.20 per run typical, no guarantee.
- **Liability.** "AS IS" without warranty. Developer not liable for costs, damages, decisions, or consequences arising from use of the tool, the model, or its outputs. Acknowledgment is required to continue.

Footer of the screen: link to `facebook/tribev2`, license text, source-code link.

### 6.3 Persistence — the single localStorage exception

```ts
localStorage["tribe_virality.disclaimer_ack"] = JSON.stringify({
  version: 1,
  ackedAt: "2026-05-08T12:34:56.789Z",
});
```

- Versioned. Bumping `DISCLAIMER_VERSION` in code re-prompts everyone.
- No PII; only the version number and a timestamp.
- This is the only `localStorage` write we make. API token, attempts, and session state never touch disk.

### 6.4 Footer disclaimer (persistent reminder)

Compact one-line disclaimer in the footer of every page:

> *Research-grade approximation · CC-BY-NC-4.0 · Non-commercial · No guarantee of real-world performance · [Read full disclaimer]*

The "Read full disclaimer" link reopens the disclaimer screen as a read-only modal (no checkbox required) so users can revisit it without losing session state.

## 7. Processing UX

This is the area that has to work hardest because Replicate prediction lifecycles span ~10s (warm) to ~150s (cold start + inference) and one-size "Loading…" feels broken.

### 7.1 Phases

| # | Phase | Replicate `status` | Typical duration | What happens |
|---|---|---|---|---|
| 1 | Upload | (none yet) | 1–10s for ≤100MB | Browser POSTs to `api.replicate.com/v1/files` |
| 2 | Queued | `starting` (warm) | 0–5s | Worker hot, just queueing |
| 2′ | Cold start | `starting` (cold) | 30–90s | Replicate provisions GPU, pulls cog image, runs `setup()` |
| 3 | Inference | `processing` | 20–120s for ≤60s video | TRIBE runs on GPU |
| 4 | Scoring + serialize | `processing` (tail) | 1–3s | Scoring pipeline runs |
| 5 | Complete | `succeeded` | — | Output JSON arrives |

### 7.2 `/processing/:predictionId` page structure

```
┌─────────────────────────────────────────────────────────────┐
│  Tribe Virality                              [● user · key] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Step 2 of 4 — Booting model                               │
│                                                             │
│   ████████████████░░░░░░░░░░░░░░░░░░░  42%                  │
│                                                             │
│   ✓ Uploaded 24.3 MB                              0:08      │
│   ✓ Submitted to Replicate                        0:02      │
│   ▶ Booting model                                 0:31      │
│     Predicting brain response                       —       │
│                                                             │
│   ┌─ What's happening ────────────────────────────────────┐ │
│   │ Replicate is starting a GPU machine and loading the   │ │
│   │ TRIBE v2 model. The first prediction after idle takes │ │
│   │ ~60 seconds; subsequent runs are much faster.         │ │
│   └───────────────────────────────────────────────────────┘ │
│                                                             │
│   [ Cancel ]                                                │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 Progress bar driver

Piecewise schedule anchored to phase boundaries. Each phase fills a fixed slice; within a phase the bar follows an asymptotic curve so it never quite hits the next slice without a real signal.

| Phase | Bar slice | Driven by |
|---|---|---|
| Upload | 0% → 25% | XHR `progress` events (real bytes / total) |
| Submitted | 25% (snap) | API response with prediction id |
| Boot (`status: starting`) | 25% → 60% | Time-based asymptotic crawl, capped |
| Inference (`status: processing`) | 60% → 95% | Time-based crawl + log-stage acceleration (§7.5) |
| Done | 100% | Snap |

Within each crawl: `p = target - (target - start) * exp(-k * t)`.

### 7.4 Polling cadence

```ts
function usePredictionPolling(predictionId: string) {
  // 0–30s: poll every 1.5s
  // 30–120s: poll every 2.5s
  // 120s+: poll every 4s
  // Exponential back-off on transient 5xx (max 3 retries).
}
```

Polls `GET /v1/predictions/{id}` returning `{status, logs, output, error, metrics}`. Stops on terminal states (`succeeded`, `failed`, `canceled`).

### 7.5 Stage markers in cog logs

`predict.py` emits machine-parseable stage lines:

```python
print("STAGE:download_video", flush=True)
print("STAGE:tribe_inference", flush=True)
print("STAGE:scoring", flush=True)
print("STAGE:done", flush=True)
```

The browser scans `prediction.logs` for the latest `STAGE:` line and uses it to override the time-based crawl with a real position bump.

### 7.6 Cold-start awareness

If the prediction has been in `status: starting` for >15s, swap the "What's happening" copy to the cold-start explanation. After the first successful prediction in a session, set a `seenWarmRun` flag and soften wording on subsequent runs ("Starting up…").

### 7.7 Cancellation

Cancel button → `POST /v1/predictions/{id}/cancel` with the user's key, route back to `/`. Toast: *"Cancelled. Replicate stops billing for this run."*

### 7.8 Error states

| Failure | UI behavior |
|---|---|
| Upload fails (network) | Inline retry on the same page, no nav |
| Upload fails (file too big / wrong type) | Bounce back to `/` with toast |
| `prediction.status === "failed"` | Banner with `prediction.error` + "Run again" button. Attempt logged with `status: error` |
| Auth fails mid-flow (401) | Drop apiKey, route to `ApiKeyGate` with toast "Token rejected by Replicate" |
| Quota exhausted (402 or specific error string) | Banner: "Replicate says you're out of credits. Add some at replicate.com/account/billing." |
| Polling timeout (>5min total) | Surface "Taking longer than expected" but don't auto-fail |
| Tab loses focus | Polling continues unless throttled; on focus regain, immediate poll |

### 7.9 UI details

- Time-elapsed counter ticks each second next to the active step.
- Single accent line at the top of the viewport does an indeterminate slide (reinforces "running").
- Tab title updates: `(42%) Tribe Virality` while running; resets on completion.
- Optional browser notification on completion if tab is unfocused (permission asked once, after first cold-start finish).
- `beforeunload` warning while a prediction is in flight: *"A prediction is running. If you leave, you'll lose track of it but Replicate will still charge for the run."*

## 8. Screens

### 8.1 Routes

| Path | Component | Guard |
|---|---|---|
| `/disclaimer` | `<Disclaimer>` | shown if no ack |
| `/key` | `<ApiKeyGate>` | shown if no key |
| `/` | `<Landing>` | requires ack + key |
| `/processing/:predictionId` | `<Processing>` | requires ack + key |
| `/results/:attemptId` | `<Results>` | requires ack + key + attempt in memory |

Direct nav to `/results/:id` after a refresh (when memory is empty) routes to `/` with toast: *"That session ended. Start a new prediction."*

### 8.2 Landing

- Centered drop zone. Constraint line: "MP4 · up to 60 seconds · up to 100MB".
- Cost hint below: *"~$0.05–0.20 per prediction · billed to your Replicate account"*.
- "How it works" three-step explainer.
- Footer disclaimer line + key chip header.

**Client-side validation before any upload starts:**
- Type ∈ `{video/mp4, video/quicktime, video/webm}`
- Size ≤ 100 MB
- Duration ≤ 60s (read via hidden `<video>` + `loadedmetadata`)

### 8.3 Results

**Layout (top to bottom):**

```
┌─────────────────────────────────────────────────────────────────┐
│  [Header: app title · key chip]                                 │
├─────────────────────────────────────────────────────────────────┤
│  Hero row                                                       │
│  ┌──────────────────────────┐  ┌──────────────────────────┐     │
│  │   User video             │  │   HeadViewer3D           │     │
│  │   <video controls>       │  │   (interactive 3D,       │     │
│  │                          │  │    drives off playhead)  │     │
│  └──────────────────────────┘  └──────────────────────────┘     │
│         "Synced with your video"                                │
├─────────────────────────────────────────────────────────────────┤
│  Score row                                                      │
│  ┌─────────────────┐  ┌────────────────────────────────────┐    │
│  │   72            │  │ Reward         ▓▓▓▓▓▓░░ 78          │   │
│  │   Virality      │  │ Emotion        ▓▓▓▓▓▓▓░ 85          │   │
│  │   +5 vs v1      │  │ Attention      ▓▓▓▓░░░░ 52          │   │
│  │ [Run another]   │  │ Novelty        ▓▓▓▓▓░░░ 61          │   │
│  │                 │  │ Social         ▓▓▓▓▓▓░░ 74          │   │
│  └─────────────────┘  └────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  BrainFrameStrip                                                │
│  Video    [thumb][thumb][thumb]...        ← drawn from <video>  │
│  Signal   ╱╲╱╲╱╲╱╲                                              │
│  Brain    [3D snap][snap][snap]...        ← captured from WebGL │
├─────────────────────────────────────────────────────────────────┤
│  Timeline (Recharts) · 5 series · playhead · click-to-seek      │
├─────────────────────────────────────────────────────────────────┤
│  [Footer disclaimer]                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Wiring:**
- Hero right pane is `HeadViewer3D` (was `<video src=brain.mp4>`). Driven by `(timeline, playheadTime)` state from the user video's `timeupdate` event.
- `BrainFrameStrip` consumes a `brainFrames: string[]` data-URL array. Captured once on Results mount via `lib/captureBrainFrames.ts`: an offscreen Three.js scene at 96×130 iterates the playhead through `frame_count` evenly-spaced timestamps and snapshots each via `renderer.domElement.toDataURL("image/jpeg", 0.85)`. Cached on the in-memory `Attempt`.
- Per-second video thumbnails are drawn from the user `<video>` via `<canvas>.drawImage(videoEl, …)` at integer seconds, lazily on first scroll into view.

**Attempts drawer (right edge):**
- In-memory `attempts[]`, newest first. Each entry: thumbnail (data URL of second 0), label, headline score.
- Click switches active attempt.
- Comparison toggle (≥2 selected): timeline overlays solid + dashed; score row shows side-by-side with delta pills.

### 8.4 Component churn

| Component | Change |
|---|---|
| `Landing.tsx` | Remove capabilities banner, add cost hint |
| `Processing.tsx` | Rewrite around `usePredictionPolling` (Replicate) |
| `Results.tsx` | Hero right pane → `HeadViewer3D`, brain frames from canvas capture |
| `VideoPair.tsx` | **Delete** |
| `usePlaybackSync.ts` | Simplify to single-video → playhead state |
| `useJobPolling.ts` | **Delete**, replaced by `usePredictionPolling.ts` |
| `useAttempts.ts` | Rewrite to read from in-memory context |
| `DropZone.tsx` | Add client-side duration validation |
| `HeadViewer3D.tsx` | Unchanged |
| `BrainFrameStrip.tsx` | Replace `api.brainFrameUrl()` with passed-in data-URL array |
| `colormap.ts`, `TimelineChart.tsx`, `ScoreRing.tsx`, `SubScoreCard.tsx`, `DeltaPill.tsx`, `TopBar.tsx`, `AttemptsDrawer.tsx`, `DisclaimerFooter.tsx` | Mostly unchanged; data source becomes the in-memory context |
| **NEW** `Disclaimer.tsx` | Full-screen ack |
| **NEW** `ApiKeyGate.tsx` | Full-screen key paste + validate |
| **NEW** `lib/replicate.ts` | Files API + Predictions API client |
| **NEW** `lib/captureBrainFrames.ts` | Offscreen WebGL capture utility |
| **NEW** `lib/AppState.tsx` | React context |
| **DELETE** `lib/api.ts`, `lib/session.ts` | |

## 9. Cog package (Replicate model)

### 9.1 Layout

```
cog/
  cog.yaml                             ← runtime config
  predict.py                           ← Predictor class
  scoring/                             ← MOVED from backend/
    __init__.py
    pipeline.py                        ← unchanged pure functions
    rois.py
    baseline.py
    constants.py
  data/
    roi_mapping.json
    baseline_stats.json
  tests/
    test_scoring_pipeline.py           ← MOVED, runs in `cog run python -m pytest`
    fixtures/
      sample.mp4                       ← tiny fixture for predict() smoke test
  README.md                            ← cog-specific build/push instructions
```

### 9.2 `cog.yaml` essentials

```yaml
build:
  gpu: true
  cuda: "12.1"
  python_version: "3.11"
  python_packages:
    - "torch>=2.4"
    - "tribev2 @ git+https://github.com/facebookresearch/tribev2.git"
    - "transformers>=4.55"
    - "numpy>=1.26"
    - "pydantic>=2"
predict: "predict.py:Predictor"
```

### 9.3 `predict.py` skeleton

```python
from cog import BasePredictor, Input, Path
from pydantic import BaseModel
from scoring.pipeline import score_predictions
from scoring.rois import load_roi_mapping
from scoring.baseline import load_baseline_stats

class Output(BaseModel):
    headline_score: int
    sub_scores: dict[str, int]
    timeline: list[dict[str, float]]
    video_duration_s: float
    frame_count: int
    model_version: str
    scoring_version: str

class Predictor(BasePredictor):
    def setup(self):
        self.roi_mask = load_roi_mapping("data/roi_mapping.json")
        self.baseline = load_baseline_stats("data/baseline_stats.json")
        self.tribe = ...  # load facebook/tribev2

    def predict(self, video: Path = Input(description="Video, ≤60s")) -> Output:
        print("STAGE:loading_video", flush=True)
        ...
        print("STAGE:tribe_inference", flush=True)
        preds = self.tribe.predict(video)        # (T, V) numpy array
        print("STAGE:scoring", flush=True)
        result = score_predictions(preds, self.roi_mask, self.baseline)
        print("STAGE:done", flush=True)
        return Output(
            headline_score=result.headline,
            sub_scores=result.sub_scores,
            timeline=result.timeline,
            video_duration_s=result.duration,
            frame_count=len(result.timeline),
            model_version="tribev2-<commit>",
            scoring_version="1.0",
        )
```

### 9.4 Push & version

The cog model is pushed to `prakhar-bhartiya/meta-tribev2-social-media-content-signal` via `cog push`. The frontend hardcodes the model owner/name and reads the latest version id at runtime via `GET /v1/models/{owner}/{name}` (one extra Replicate call per session, cached). When the model is republished, frontends pick up the new version on next session without redeployment.

## 10. Deletion list

### 10.1 Top-level paths to remove entirely

```
backend/                               ← entire directory
  conftest.py
  pyproject.toml
  scripts/
  src/tribe_virality/
    __init__.py
    main.py
    config.py
    capabilities.py
    db.py
    models.py
    schemas.py
    routes/
      __init__.py
      attempts.py
      health.py
      jobs.py
      upload.py
    jobs/
      __init__.py
      queue.py
    inference/
      __init__.py
      backend.py
      factory.py
      hosted.py
      local_mps.py
      mock.py
    media/
      __init__.py
      brain_render.py
      brain_frames.py
      ffprobe.py
      thumbnails.py
    scoring/                           ← MOVED to cog/scoring/, then this copy deleted
    data/                              ← MOVED to cog/data/, then this copy deleted
  tests/
    __init__.py
    unit/__init__.py
    unit/test_scoring_pipeline.py     ← MOVED to cog/tests/, then this copy deleted
  cache/                               ← gitignored runtime dir
  data/                                ← gitignored runtime dir

frontend/src/lib/
  api.ts
  session.ts

frontend/src/hooks/
  useJobPolling.ts

frontend/src/components/
  VideoPair.tsx
```

### 10.2 README.md sections to delete

- "Inference Backends" table and all `TRIBE_BACKEND` references
- "Capability detection & banner" section
- "Using the local backend (Apple Silicon / CUDA GPU)" section
- "Project Structure" `backend/` block (replaced with cog/ + frontend/)
- Backend pytest reference under "Running Tests" (replaced with cog test command)

### 10.3 Other doc cleanups

- `docs/mps-status.md` — delete (orphaned by removal of `local_mps.py`).
- `tribe_demo.ipynb` — keep as reference for cog implementation.
- `.gitignore` — drop `backend/data/`, `backend/cache/`, `backend/.pytest_cache/`, MPS-specific entries.

## 11. Testing strategy

### 11.1 Cog package (Python, runs in `cog run python -m pytest`)

1. **Scoring pipeline (pure function).** Moved test, asserts exact sub-scores and headline against fixture preds + baseline. Unchanged from current backend tests.
2. **ROI mapping loader.** Moved test, asserts vertex-count sanity per bucket.
3. **`predict()` schema smoke test.** Runs against a tiny fixture video; asserts all output fields present and within expected ranges. Skipped if `cog run` is unavailable in CI.

### 11.2 Frontend (Vitest + React Testing Library)

4. **Disclaimer flow.** Renders, "Continue" disabled until checkbox, on accept writes `disclaimer_ack` localStorage and routes to `/key`. Bumping `DISCLAIMER_VERSION` re-prompts.
5. **ApiKeyGate.** Renders when `apiKey === null`. On submit: mocks `fetch` to `api.replicate.com/v1/account` → 200 stores key + routes onward; 401 shows inline error; 5xx shows network error.
6. **`replicateFetch` helper.** Asserts `Authorization` header present, host pin, and that `Authorization` is scrubbed from any Error message thrown.
7. **`usePredictionPolling`.** Fakes `fetch` returning sequential prediction states (`starting` → `processing` → `succeeded`); asserts polling cadence, stage transitions, cleanup on unmount, and back-off on 5xx.
8. **Progress bar driver.** Given a sequence of `(status, elapsed)` ticks, asserts the bar fill stays monotonic and within the phase slices defined in §7.3.
9. **`captureBrainFrames`.** Renders an offscreen scene with a fixture timeline; asserts returned data-URL count == requested frame count and each is a valid `image/jpeg` data URI.
10. **`BrainFrameStrip`.** Renders correctly given a `brainFrames: string[]` array (no HTTP).
11. **`HeadViewer3D` smoke.** Mounts without crashing given a mocked GLB loader and a fixture timeline.
12. **`AppState` reducers.** `forgetKey()` clears apiKey AND attempts AND currentJobId; `addAttempt()` prepends; `setCurrentJob()` semantics.
13. **Routing guards.** Direct nav to `/results/:id` with empty memory routes to `/` with toast.

### 11.3 Manual / E2E gate

14. **Smoke run against real Replicate.** The developer runs one prediction end-to-end on the deployed Hostinger frontend with a real key + 10s sample video before tagging a release. Documented as a release checklist item, not automated.

## 12. Milestones

1. **M1 — Cog skeleton.** `cog.yaml`, `predict.py` returning a synthetic plausible timeline, scoring + ROI tests passing in `cog run`. Pushable to Replicate. No real TRIBE yet. ← unblocks frontend work.
2. **M2 — Real TRIBE in cog.** Wire `facebook/tribev2`, run on Replicate GPU, validate output shape end-to-end. Push to `prakhar-bhartiya/meta-tribev2-social-media-content-signal`.
3. **M3 — Frontend deletions.** Remove `backend/`, `lib/api.ts`, `lib/session.ts`, `useJobPolling.ts`, `VideoPair.tsx`, capability banner. Strip relevant README sections + `docs/mps-status.md`. App will be broken at this point — M4 immediately follows.
4. **M4 — Disclaimer + ApiKeyGate + AppState.** New routes, new context. App boots into disclaimer → key gate → empty Landing.
5. **M5 — Replicate client + upload + processing UX.** `lib/replicate.ts`, `usePredictionPolling`, the Section 7 progress UX. Landing → Processing flow works end-to-end against the M2 cog model.
6. **M6 — Results wiring.** Hero (video + HeadViewer3D), score row, timeline. Route to Results on succeeded.
7. **M7 — Brain-frame strip via canvas capture.** `captureBrainFrames.ts` + BrainFrameStrip rewire.
8. **M8 — Attempts drawer + comparison.** In-memory history, delta pills, comparison overlay.
9. **M9 — Hostinger deploy.** Vite build → static `dist/` served by nginx. README rewritten end-to-end.

M1–M2 are independent of the frontend and may parallelize with M3–M4.

## 13. Documentation deliverables

- **`README.md`** — rewritten: new architecture, no `TRIBE_BACKEND`, no Python backend setup, just `npm install` / `npm run dev`, plus a "Bring your own Replicate key" section.
- **`cog/README.md`** — how to build, test (`cog run`), and push the cog model.
- **`docs/REPLICATE_SETUP.md`** — user-facing onboarding (linked from disclaimer + key gate): create account, add credits, create token, paste.

## 14. Open assumptions

- **Replicate CORS.** `api.replicate.com` is assumed to permit cross-origin requests from arbitrary browser origins for the Files, Predictions, and Account endpoints with `Authorization` headers. Verified in the M5 spike before the design depends on it.
- **Replicate Files API limits.** Free-tier accounts may have file-size or rate limits below our 100 MB cap. The Landing screen will surface any 4xx response from `POST /v1/files` clearly so the user can act on it.
- **TRIBE v2 cog buildability.** `tribev2 @ git+...` is assumed installable inside cog's CUDA 12.1 / Python 3.11 image. Verified in M1.
- **GLB asset hosting.** The brain GLB files in `frontend/public/models/` ship with the static bundle. No external CDN dependency at runtime.
- **Disclaimer ack storage.** A single localStorage key is acceptable as the legal-acknowledgment record. Counsel-grade review is out of scope.
