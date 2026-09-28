# Feature roadmap — what is not in the app, and why

The Phase 1 baseline (`design/specs/phase1-baseline.md`) consolidated the
app around one path: Projects → Footage → Brief → Rough cut → Story →
Export. The "Creative tools" page that used to list seven feature cards is
gone: three of them were second doors to things the workspace already does
(*Plan my edit* = the chat; *Titles & motion* = Words on screen → *Add
titles for me*; *Borrow a feeling* = *Reference* in the header), and four
were disabled cards. Those four are recorded here, not in the product, so
nothing in the app looks like a feature that isn't one.

## Ideas from the September 20 recordings, not built

Descriptions of third-party implementations are research guidance, not
proof of their internal architecture. None of these has a pipeline, a
provider, or a UI. Each would need explicit consent and cost decisions
before it becomes a screen.

| Idea | Source recording | What it would take | Why it waits |
| --- | --- | --- | --- |
| Camera motion (animate a still moment) | ScreenRecording_09-20-2026 19-16-28_1.MP4 | An image-to-video provider, motion constraints, preview and subject-consistency checks | Generates frames the creator didn't film — against the non-goal in CLAUDE.md unless kept as a clearly separate, opt-in mode |
| Try another version (variants of the hook) | ScreenRecording_09-20-2026 19-29-16_1.MP4 | Reusable scene templates, timing alignment, non-destructive alternate versions | Versions need a project model first (now exists: `projects.py`); the storyboard's op log can branch, but the UI for comparing versions is not designed |
| My on-screen character (presenter / cartoon narrator) | ScreenRecording_09-20-2026 19-30-49_1.MP4 | Voice and avatar providers, a consent step before any cloning, composition | Paid providers and consent flow; generated media is a separate mode by design |
| Find the supporting shots (B-roll suggestions) | ScreenRecording_09-20-2026 19-20-48_1.MP4 | Beat/transcript understanding, retrieval over the creator's own index first, approval before insertion | Start with the creator's own footage: the index already has labels (macOS) and per-second signals; a "show what I'm talking about" suggestion is the first honest version |

## What Phase 1 deliberately left out (see the parity matrix)

- Semantic search over footage by content ("every shot of the product on
  the table"): needs embeddings and a model; the index has no text
  descriptions yet.
- Cross-platform speech-to-text: transcripts stay macOS-only and opt-in
  (talking-to-camera mode). The default path needs no transcript.
- Multiple aspect ratios per export: the export follows the footage's
  shape; a format choice is a small addition once calibrated framing exists.
- External agents (MCP): the ops interface in `board.py` is the right
  boundary for it; nothing is exposed yet.

## Next implementation order

1. Calibrate thresholds on real footage (the rule that matters most).
2. B-roll suggestions from the creator's own index, with approval.
3. Versions of a project (branch the op log), then variants.
4. Paid generation only after provider, cost and consent choices are explicit.
