# Creative tools — recording-inspired feature previews

The seven feature cards translate the user's September 20 recordings into
beginner-facing workflows. Plan my edit is connected to VibeCut's real,
reversible storyboard operation engine. The remaining six are disabled and
labelled Coming soon until their underlying pipelines exist. Descriptions of
third-party implementations are research guidance, not proof of their internal
architecture or installed integrations.

| Button | Source recording | Research inspiration | Integration still needed |
| --- | --- | --- | --- |
| Camera motion | ScreenRecording_09-20-2026 19-16-28_1.MP4 | Named motion presets; exact product unidentified | Image-to-video provider, motion constraints, preview and subject-consistency checks |
| Plan my edit — live | ScreenRecording_09-20-2026 19-17-24_1.MP4 | Hypit agent video workflow | Connected to `/api/chat`: direction becomes validated storyboard operations, recorded diffs and Undo. Requires footage, rough-cut approval and configured AI for edits to an existing board |
| Titles & motion | export_1789946152141.MOV | HyperFrames HTML/CSS-to-video | Deterministic reusable graphic components, profile-to-design-token mapping, rendering |
| Borrow a feeling | ScreenRecording_09-20-2026 19-32-41_1.MP4 | VidMuse reference packaging | Reference ingestion and analysis, editable style attributes, approval before application |
| Try another version | ScreenRecording_09-20-2026 19-29-16_1.MP4 | Hypit reference-video variants | Semantic scene templates, timing alignment and non-destructive alternate versions |
| My on-screen character | ScreenRecording_09-20-2026 19-30-49_1.MP4 | Fish Audio + HeyGen + HyperFrames | Voice/avatar services, consent before cloning, alignment and composition; cartoon output needs a suitable provider |
| Find the supporting shots | ScreenRecording_09-20-2026 19-20-48_1.MP4 | Local video agent; exact product unidentified | Beat/transcript understanding, footage retrieval, optional licensed stock/generation, approval before insertion |

## Current boundary

- Plan my edit executes against the current project. It returns to the editor only after the backend accepts the request; errors remain visible in its dialog.
- Browser storage is per origin and does not sync with an account or backend.
- The last successful guided-edit request captures the profile at execution time,
  so later profile edits do not silently rewrite the recorded request.
- Reference analysis is not available yet; the corresponding card is disabled.
- The real-footage editing engine stays separate from optional generated-media modes.
- No third-party packages or API credentials are needed for this planning interface.

## Next implementation order

1. Add deterministic title/caption previews driven by creator style.
2. Suggest B-roll from the user's own indexed footage, with approval.
3. Integrate reference analysis and versioned style cards.
4. Add paid generation only after provider, cost and consent choices are explicit.
