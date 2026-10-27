# Character motion v2

Assets generated with the built-in Imagegen tool, normalized with the Sprite Pipeline helpers. Original atlas and portraits are preserved.

- `apps/web/public/office/characters-motion-v2.png`: transparent 1536 × 768 atlas; 12 columns × 6 rows; 128px cells. Columns 0–7 walk, 8–9 sit transition, 10–11 seated typing.
- `apps/web/public/office/characters-motion-v2-preview.png`: static contact sheet.
- Row order: Planner, Frontend, Backend, QA, DevOps, Reviewer.
- Walking cycles at 12 fps, with reduced body bob. Left-facing walking mirrors UVs within the same atlas cell.
- Sitting requires a live connection, running/queued/awaiting_approval state, stopped movement, and arrival at the assigned desk. Typing animates only while running. Offline, idle, failed, blocked, completed states do not trigger work poses.
- Seated artwork includes a chair, with row-specific alignment to the existing desks. This is visual presentation only; no agent tasks are created or run.
- Browser visual review used an isolated fixture in `work/motion-preview.tsx` without a backend connection. The fixture is excluded from the shipped build.

## Prompt set (built-in Imagegen)

Walk: Use the approved six-character atlas as an identity reference. Preserve every face, outfit, palette and pixel-art silhouette. Generate one transparent 8-column, 6-row atlas of complete progressive walk cycles, one identity per row. Right-facing three-quarter full-body sprites, shared scale and bottom-center anchors; contact, down, passing, up and opposite-leg phases. Crisp pixel clusters, no labels, grid, scenery or shadows.

Seated: Use the same approved atlas. Generate a transparent 4-column, 6-row sheet, same row identities. Four progressive work poses: bending to sit, lowering onto a dark navy office chair, seated typing and alternate typing hands. Face away in three-quarter view toward the desk. Preserve outfits and hair, keep chair and full figure inside each cell. No actual desk or monitor, scenery, text or grid.

## Validation

Production build passed; 168 office checks passed, including expanded atlas left/right UV bounds, desk-only seating, offline behavior, work states, sitting/typing frames, furniture avoidance and task return. Walking and seated assets inspected in the browser scene.
