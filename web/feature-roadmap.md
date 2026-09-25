# Creative tools — recording-inspired feature previews

The seven feature buttons translate the user's September 20 recordings into
beginner-facing workflows. They currently save/download structured briefs,
including a creator-profile snapshot. They do not claim to generate videos.
Descriptions of underlying third-party implementations are research guidance,
not proof of their internal architecture or installed integrations.

| Button | Source recording | Research inspiration | Integration still needed |
| --- | --- | --- | --- |
| Camera motion | ScreenRecording_09-20-2026 19-16-28_1.MP4 | Named motion presets; exact product unidentified | Image-to-video provider, motion constraints, preview and subject-consistency checks |
| Plan my edit | ScreenRecording_09-20-2026 19-17-24_1.MP4 | Hypit agent video workflow | Translate the brief to validated existing storyboard operations; retain diffs and undo |
| Titles & motion | export_1789946152141.MOV | HyperFrames HTML/CSS-to-video | Deterministic reusable graphic components, profile-to-design-token mapping, rendering |
| Borrow a feeling | ScreenRecording_09-20-2026 19-32-41_1.MP4 | VidMuse reference packaging | Reference ingestion and analysis, editable style attributes, approval before application |
| Try another version | ScreenRecording_09-20-2026 19-29-16_1.MP4 | Hypit reference-video variants | Semantic scene templates, timing alignment and non-destructive alternate versions |
| My on-screen character | ScreenRecording_09-20-2026 19-30-49_1.MP4 | Fish Audio + HeyGen + HyperFrames | Voice/avatar services, consent before cloning, alignment and composition; cartoon output needs a suitable provider |
| Find the supporting shots | ScreenRecording_09-20-2026 19-20-48_1.MP4 | Local video agent; exact product unidentified | Beat/transcript understanding, footage retrieval, optional licensed stock/generation, approval before insertion |

## Current boundary

- A brief is a request, not an executed job. No job progress or generated assets are fabricated.
- Browser storage is per origin and does not sync with an account or backend.
- A saved brief captures the profile at configuration time, so later profile edits
  do not silently change old briefs. Reopen and save to attach the current profile.
- Reference URLs are optional HTTP(S) bookmarks, not fetched or analyzed.
- The real-footage editing engine stays separate from optional generated-media modes.
- No third-party packages or API credentials are needed for this planning interface.

## Next implementation order

1. Feed an approved guided-edit brief into the existing reversible operation engine.
2. Add deterministic title/caption previews driven by creator style.
3. Suggest B-roll from the user's own indexed footage, with approval.
4. Integrate reference analysis and versioned style cards.
5. Add paid generation only after provider, cost and consent choices are explicit.
