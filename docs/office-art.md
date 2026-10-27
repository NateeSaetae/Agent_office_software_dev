# Pixel Office — visual update

This update changes the office presentation only. Project APIs, provider authentication, task execution, approval rules, and database state are unchanged.

## Shipped experience

- Full viewport office beneath a fixed top navigation bar.
- A nonblocking, collapsible Agent Status panel on the left.
- Detailed environment artwork matching the supplied reference: meeting room, city windows, lounge, coffee bar, six workstations, books, plants, and server racks.
- Six distinct character designs, shared between world sprites, status portraits, and detail drawers.
- Four normalized walking frames per character, idle breathing, visible faces, and horizontal facing changes.
- Idle-only wandering among coffee, meeting, lounge, and aisle waypoints, with pauses and furniture-aware A* routes.
- Idle actors yield near other characters and choose another destination when crowded.
- Actual running/queued/waiting agents return to their assigned desk. Visual activity is derived from backend state and events.
- Idle roaming is cosmetic: it never creates tasks, emits fabricated backend events, or changes progress.
- A pause control and automatic reduced-motion support.
- The environment preserves its aspect ratio. Drag the scene to look around on narrower windows.
- Clicking a visible character or its status card opens the existing real agent details.
- Recent activity and active-project overlays still use backend data.

The environment is a detailed pre-rendered 2.5D pixel-art plate displayed through React Three Fiber. Characters and interaction remain separate animated scene objects. This choice replaces the former block-based 3D art with a much closer match to the reference.

## Art assets and generation

Mode: built-in ImageGen, using the user’s attached concept image as the visual reference. No API-key generation path was used.

Final project assets:
- apps/web/public/office/office-environment.png — 1672×941 environment.
- apps/web/public/office/characters-atlas.png — 512×768 RGBA atlas, four columns and six rows.
- apps/web/public/office/planner-portrait.png
- apps/web/public/office/frontend-portrait.png
- apps/web/public/office/backend-portrait.png
- apps/web/public/office/qa-portrait.png
- apps/web/public/office/devops-portrait.png
- apps/web/public/office/reviewer-portrait.png

Sprite normalization uses a shared global scale, transparent backgrounds, nearest-neighbor sampling, and bottom-center anchors. The original six-row generated strip was normalized using the sprite-pipeline helper’s content-cropping and frame-composition functions. Portraits are crops from the shipped standing frame, preserving identity.

## Final prompt set

### Environment prompt

Use case: precise-object-edit. Production game background for Natee's Software House. Use the attached image as the primary ART AND LAYOUT reference. Produce a beautiful highly detailed HD-2D PIXEL ART OFFICE ENVIRONMENT PLATE, wide 16:9 landscape, with the exact cozy warm orange wood floor, midnight blue brick, luminous city windows, soft cinematic warm lamps, tiny textured books and lush leafy plants. Remove ALL user interface overlays completely: no navbar, no sidebar, no status boxes, no UI frames, no task panels, no floating labels. Reconstruct complete room where the overlays used to be. Remove ALL human characters and all cats/animals; leave chairs empty. The camera is nearly frontal, elevated RPG cutaway perspective like the reference, not diamond-shaped floating dollhouse. FILL THE ENTIRE IMAGE edge to edge with the OFFICE, no outer black space, no blank canvas. Fixed composition for later animation: top 34% of image contains rear wall: meeting room on left 0-27%, orange lounge sofa under huge city window center 36-67%, coffee bar right 78-99%. Main walkable warm wooden floor occupies lower 66%. Exactly SIX empty workstation desks in two aligned rows of three: centers in image coordinates (34%,47%), (54%,47%), (75%,47%), (34%,72%), (54%,72%), (75%,72%). Dual monitors with detailed code/design screens, keyboards, mugs, notebooks and small plants; leave ample unobstructed walking aisles between all desks. Far left lower lounge blue sofa and guitar, far right lower server racks, lower edge glass entry partitions and welcome mat. KEEP ALL PERSON-SIZED WALKING AISLES CLEAR. Charming intricate pixel clusters and restrained outlines at high resolution, premium 1990s RPG background painting with modern HD lighting. No flat vector, no low-poly 3D boxes, no people, no letters or text labels except subtle environmental signage 'MEETING ROOM' and 'COFFEE'. This is only the environment bitmap; real interactive characters and interface will be overlaid separately. Preserve the visual quality and warmth of the reference.

### Character prompt

Production pixel-art CHARACTER ANIMATION SPRITE SHEET for the attached cozy software office RPG. Use the character portraits in the reference as design direction only, never reproduce the UI or scenery. Create ONE transparent PNG sprite sheet in portrait 2:3 aspect ratio, exactly FOUR COLUMNS by SIX ROWS. Each of 24 equal square cells contains ONE full-body cute detailed chibi pixel-art software developer, with visible expressive face, crisp dark outlined pixel clusters, warm skin shading, beautifully shaded hair and clothing. NO scenery, NO ground, NO shadows extending outside figure, NO text, NO labels, NO cell borders. Actual alpha transparency everywhere outside each character. All figures same scale, same head size, same baseline, same frontal 3/4 facing direction toward viewer. Feet fully visible, full body with arms and legs separated. Leave generous transparent padding between cells. Four columns of each row show a coherent four-frame walking cycle of THAT SAME character: left foot forward, feet passing/standing, right foot forward, feet passing/standing. Preserve identity EXACTLY across each row. Six distinct identities, each row has SAME hair/outfit for its 4 frames: ROW1 Planner: tousled brown hair, round glasses, cream cardigan over navy shirt, brown trousers, notebook at belt. ROW2 Frontend: shaggy black hair, teal hoodie, dark blue jeans, white sneakers, small headphones around neck. ROW3 Backend: short auburn hair and subtle moustache, forest green shirt with rolled sleeves, dark trousers, brown shoes. ROW4 QA: black bob hair, white lab coat over mustard t-shirt, navy trousers, amber shoes, red hair clip. ROW5 DevOps: blue baseball cap, dark navy jacket with bright blue patches, grey cargo trousers, dark boots, small tool pouch. ROW6 Reviewer: dark side-parted hair, rectangular glasses, burgundy vest over pale shirt, charcoal trousers, neat dark shoes. High-quality detailed 64-to-96-pixel-style figures enlarged with clean nearest-neighbor pixel edges; visibly readable faces and individual costumes. NOT 3D models, NOT vectors, NOT blurry illustrations. Exactly 6 rows x 4 columns. A usable game animation asset, not a poster.

## Verification

Run from apps/web:

    npm run test:office
    npm run build

The office checks cover all desk-to-break-spot routes, furniture avoidance, idle wandering, pause behavior, return to desk during a real task, offline freezing, and reduced-motion behavior. Browser QA covers the top navigation, status panel, real detail drawer, character selection, and pause/resume.

This update does not claim nine separately authored action animations or free 3D camera rotation. Walking frames and idle motion are shipped; actual work gets an event-driven state badge and bubble.

### Left-facing walk frames

Left-facing movement mirrors each four-frame walk cycle inside its own atlas cell using texture UVs. Sprite scale remains positive because Three.js Sprite shaders discard the sign of the scale. The same UV transform is used by alpha hit testing. The office checks cover every character row and animation frame in both directions, plus facing changes during movement.
