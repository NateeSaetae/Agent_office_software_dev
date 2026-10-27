# Workspace visual design

Tasks, Agents, Projects, Activity and Settings share a light blue/white interface. The full-screen pixel-art Office retains its own scene and immersive controls.

- Background: #f4f7fc with a restrained pale cyan highlight.
- Surfaces: white, soft blue borders, 20–24px corner radii.
- Primary text: #142b50; primary action: #1766ed; cyan accents for focus and active navigation.
- Main body: 16px; task titles: 17px; secondary labels: 13–15px; headings: 30–38px.
- Buttons, search inputs and project selectors use capsule shapes. Multiline fields use rounded rectangles to preserve writing space.
- Keyboard focus is visible. Motion transitions are disabled when reduced motion is requested.

## Bounded content

Project briefs, workspace paths, task descriptions, acceptance criteria, results, errors, source diffs and logs have bounded scroll areas. Task columns scroll independently. Search filters Tasks and Activity using existing loaded data; it never starts agent runs.

## Browser validation

- All five workspace pages inspected in the browser at 1600px desktop width.
- Tasks search filtered ten isolated fixture tasks down to one; the column count updated to one.
- Activity search matched an actual event and showed an empty state for no matches.
- A 1,166px task description remained in a 142px-high area and scrolled with Page Down.
- A task column containing 4,901px of cards remained 392px high and scrolled independently.
- A 1,971px project brief remained in a 144px-high area before the final compact brief adjustment.
- Tasks desktop body measured 1600×1000 with no document overflow in either direction.
- Mobile layout checked separately; navigation wraps into its own scrollable row, and cards stack vertically.
- Create/delete dialogs inspected without creating or deleting user projects.
- Layout fixtures are stored in work/qa-workspace-theme, separate from the user's database. No AI runs were started for visual testing.

Verification: npm run build (TypeScript and Vite) and interactive browser checks. No backend behavior changed.
