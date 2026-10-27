const fs = require("node:fs"),
  path = require("node:path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, "../../.."),
  ts = require(path.join(root, "apps/web/node_modules/typescript"));
const out = path.join(root, "work/office-check");
fs.mkdirSync(out, { recursive: true });
for (const file of ["navigation", "simulation", "animation"]) {
  const source = fs.readFileSync(
    path.join(root, "apps/web/src/office", file + ".ts"),
    "utf8",
  );
  let js = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.CommonJS,
    },
  }).outputText;
  js = js.replace('require("./navigation")', 'require("./navigation.cjs")');
  fs.writeFileSync(path.join(out, file + ".cjs"), js);
}
const { DESKS, BREAK_SPOTS, findPath, isWalkable } = require(
  path.join(out, "navigation.cjs"),
);
const { OfficeSimulation } = require(path.join(out, "simulation.cjs"));
const { applyCharacterFrame, shouldSitAtDesk, seatedFrame } = require(
  path.join(out, "animation.cjs"),
);
const THREE = require(path.join(root, "apps/web/node_modules/three"));
let checks = 0;
// Use Three's real UV transform: left must mirror the same frame, never a
// neighboring animation frame or another agent's row.
for (let row = 0; row < 6; row++) {
  for (let frame = 0; frame < 4; frame++) {
    const texture = new THREE.Texture();
    const sample = (facing, x, y) => {
      applyCharacterFrame(texture, frame, row, facing);
      texture.updateMatrix();
      return texture.transformUv(new THREE.Vector2(x, y));
    };
    for (const [x, y] of [
      [0.1, 0.2],
      [0.5, 0.5],
      [0.9, 0.8],
    ]) {
      const right = sample(1, 1 - x, y);
      const left = sample(-1, x, y);
      assert.ok(Math.abs(left.x - right.x) < 1e-12);
      assert.ok(Math.abs(left.y - right.y) < 1e-12);
      assert.ok(left.x > frame / 4 && left.x < (frame + 1) / 4);
      assert.ok(left.y > row / 6 && left.y < (row + 1) / 6);
    }
    const right = sample(1, 0.1, 0.5);
    const left = sample(-1, 0.1, 0.5);
    assert.ok(left.x > right.x, "Left-facing frame was not mirrored");
    texture.dispose();
    checks++;
  }
}
// Expanded atlas must keep each left/right frame inside its own cell.
for (let row = 0; row < 6; row++)
  for (let frame = 0; frame < 12; frame++) {
    const texture = new THREE.Texture();
    for (const facing of [-1, 1]) {
      applyCharacterFrame(texture, frame, row, facing, 12);
      texture.updateMatrix();
      const uv = texture.transformUv(new THREE.Vector2(0.2, 0.5));
      assert.ok(uv.x > frame / 12 && uv.x < (frame + 1) / 12);
      assert.ok(uv.y > row / 6 && uv.y < (row + 1) / 6);
    }
    texture.dispose();
    checks++;
  }
for (const status of ["running", "queued", "awaiting_approval"]) {
  assert.equal(shouldSitAtDesk(true, status, false, DESKS[0], DESKS[0]), true);
  assert.equal(shouldSitAtDesk(true, status, true, DESKS[0], DESKS[0]), false);
  assert.equal(
    shouldSitAtDesk(false, status, false, DESKS[0], DESKS[0]),
    false,
  );
  assert.equal(
    shouldSitAtDesk(true, status, false, BREAK_SPOTS[0], DESKS[0]),
    false,
  );
  checks++;
}
for (const status of ["idle", "failed", "blocked", "completed"])
  assert.equal(shouldSitAtDesk(true, status, false, DESKS[0], DESKS[0]), false);
assert.equal(seatedFrame(0, 0, 0, true), 8);
assert.equal(seatedFrame(0.6, 0, 0, true), 9);
assert.equal(seatedFrame(1, 0, 0, true), 10);
assert.equal(seatedFrame(1, 0.25, 0, true), 11);
assert.equal(seatedFrame(1, 0.25, 0, false), 10);
checks++;
const directionSim = new OfficeSimulation(["planner"]);
directionSim.sync([{ id: "planner", status: "idle" }], true);
const walker = directionSim.actors[0];
walker.nextBreak = Infinity;
walker.path = [[walker.position[0] - 0.02, walker.position[1]]];
directionSim.update(1 / 60, true, false);
assert.equal(walker.facing, -1);
walker.path = [[walker.position[0], walker.position[1] + 0.02]];
directionSim.update(1 / 60, true, false);
assert.equal(walker.facing, -1, "Vertical movement should preserve facing");
walker.path = [[walker.position[0] + 0.02, walker.position[1]]];
directionSim.update(1 / 60, true, false);
assert.equal(walker.facing, 1);
checks++;
for (const p of [...DESKS, ...BREAK_SPOTS]) {
  assert.ok(isWalkable(p), JSON.stringify(p));
  checks++;
}
for (const desk of DESKS)
  for (const target of BREAK_SPOTS) {
    const route = findPath(desk, target);
    assert.ok(route.length > 0, "Missing route " + desk + " -> " + target);
    assert.ok(route.every(isWalkable));
    checks++;
  }
const ids = ["planner", "frontend", "backend", "qa", "devops", "reviewer"];
const sim = new OfficeSimulation(ids),
  idle = ids.map((id) => ({ id, status: "idle" }));
sim.sync(idle, true);
for (let i = 0; i < 1200; i++) {
  sim.update(1 / 60, true, false);
  for (const a of sim.actors)
    assert.ok(
      isWalkable(a.position),
      "Actor crossed furniture " + JSON.stringify(a.position),
    );
}
assert.ok(
  sim.actors.every(
    (a, i) =>
      Math.hypot(a.position[0] - DESKS[i][0], a.position[1] - DESKS[i][1]) >
      0.01,
  ),
);
checks++;
const before = JSON.stringify(sim.actors.map((a) => a.position));
for (let i = 0; i < 60; i++) sim.update(1 / 60, false, false);
assert.equal(JSON.stringify(sim.actors.map((a) => a.position)), before);
checks++;
sim.sync(
  idle.map((a, i) =>
    i === 0 ? { ...a, status: "running", task: { id: "real-task" } } : a,
  ),
  true,
);
for (let i = 0; i < 1500; i++) sim.update(1 / 60, false, false);
assert.ok(
  Math.hypot(
    sim.actors[0].position[0] - DESKS[0][0],
    sim.actors[0].position[1] - DESKS[0][1],
  ) < 0.001,
);
assert.equal(sim.actors[0].status, "running");
checks++;
sim.sync(idle, false);
const offline = JSON.stringify(sim.actors.map((a) => a.position));
for (let i = 0; i < 120; i++) sim.update(1 / 60, true, false);
assert.equal(JSON.stringify(sim.actors.map((a) => a.position)), offline);
checks++;
sim.sync(idle, true);
const reduced = JSON.stringify(sim.actors.map((a) => a.position));
for (let i = 0; i < 120; i++) sim.update(1 / 60, true, true);
assert.equal(JSON.stringify(sim.actors.map((a) => a.position)), reduced);
checks++;
console.log(
  checks +
    " office checks passed: left/right atlas frames, facing changes, reachable routes, furniture avoidance, idle roaming, pause, task return, offline and reduced motion.",
);
