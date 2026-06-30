---
id: experience.editor-ux
name: Editor UX
type: experience
layer: L5
status: wip
owners: [sam.rivera]
depends_on:
  - "[[capture]]"
unlocks: []
code_refs:
  - notewell/src/web/editor/
  - notewell/src/web/editor/toolbar.tsx
---

## Why it matters

The editor is where users spend the majority of their time in Notewell. A slow or unintuitive editor erodes trust in the whole product. Good editor UX makes capture feel effortless and encourages users to reach for Notewell first.

## Current state

Markdown editor with live preview is shipped. Block-style editing (drag-to-reorder paragraphs) is wip. Tagging from the editor toolbar is placeholder. Mobile editor is not yet started.

## Key decisions

- Markdown as the canonical format: portable, diff-friendly, storage-efficient.
- Live preview in split-pane by default; distraction-free single-pane toggle planned.

## Open questions

- Should we support rich embeds (images, tables) in v1 or defer to v2?
- What is the minimum viable mobile editor experience?

## References

- [[capture]] — parent pillar
- [[tagging]] — tag input will live in the editor toolbar
- [[solo-user]] — primary persona driving editor requirements
