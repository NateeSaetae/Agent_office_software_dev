import { BREAK_SPOTS, DESKS, findPath, type Point } from "./navigation";
export type Actor = {
  id: string;
  position: Point;
  path: Point[];
  moving: boolean;
  facing: number;
  frame: number;
  phase: number;
  nextBreak: number;
  blockedFor: number;
  status: string;
  taskId?: string;
  destination: Point;
};
export class OfficeSimulation {
  actors: Actor[];
  time = 0;
  online = false;
  roaming = true;
  private seed = 23173;
  constructor(ids: string[]) {
    this.actors = ids.map((id, i) => ({
      id,
      position: [...DESKS[i]] as Point,
      path: [],
      moving: false,
      facing: 1,
      frame: 2,
      phase: i * 1.17,
      nextBreak: 1.8 + i * 1.4,
      blockedFor: 0,
      status: "idle",
      destination: [...DESKS[i]] as Point,
    }));
  }
  private random() {
    this.seed = (this.seed * 1664525 + 1013904223) >>> 0;
    return this.seed / 4294967296;
  }
  sync(
    agents: { id: string; status: string; task?: { id: string } }[],
    online: boolean,
  ) {
    this.online = online;
    for (const a of this.actors) {
      const actual = agents.find((v) => v.id === a.id);
      if (!actual) continue;
      if (actual.status !== a.status || actual.task?.id !== a.taskId) {
        a.status = actual.status;
        a.taskId = actual.task?.id;
        const i = this.actors.indexOf(a);
        if (a.status !== "idle") {
          a.destination = DESKS[i];
          a.path = findPath(a.position, a.destination);
        } else {
          a.path = [];
          a.nextBreak = this.time + 1 + this.random() * 3;
        }
      }
    }
  }
  update(dt: number, roaming: boolean, reducedMotion: boolean) {
    this.time += Math.min(dt, 0.05);
    this.roaming = roaming;
    for (const a of this.actors) {
      const idle = a.status === "idle";
      if (!this.online || reducedMotion || (!roaming && idle)) {
        a.moving = false;
        a.frame = 2;
        continue;
      }
      if (idle && a.path.length === 0 && this.time >= a.nextBreak) {
        const options = BREAK_SPOTS.filter(
          (p) =>
            Math.hypot(p[0] - a.position[0], p[1] - a.position[1]) > 0.09 &&
            !this.actors.some(
              (other) =>
                other !== a &&
                (Math.hypot(
                  other.destination[0] - p[0],
                  other.destination[1] - p[1],
                ) < 0.08 ||
                  Math.hypot(
                    other.position[0] - p[0],
                    other.position[1] - p[1],
                  ) < 0.08),
            ),
        );
        if (!options.length) {
          a.nextBreak = this.time + 2;
          continue;
        }
        a.destination = options[Math.floor(this.random() * options.length)];
        a.path = findPath(a.position, a.destination);
        a.nextBreak = this.time + 7 + this.random() * 7;
      }
      const next = a.path[0];
      a.moving = !!next;
      if (next) {
        if (idle) {
          const blocked = this.actors.some(
            (other) =>
              other !== a &&
              Math.hypot(
                (other.position[0] - a.position[0]) * 1.77,
                other.position[1] - a.position[1],
              ) < 0.085 &&
              Math.hypot(
                (other.position[0] - next[0]) * 1.77,
                other.position[1] - next[1],
              ) <
                Math.hypot(
                  (other.position[0] - a.position[0]) * 1.77,
                  other.position[1] - a.position[1],
                ),
          );
          if (blocked) {
            a.moving = false;
            a.frame = 2;
            a.blockedFor += dt;
            if (a.blockedFor > 1.2) {
              a.path = [];
              a.nextBreak = this.time + 0.2 + this.random();
              a.blockedFor = 0;
            }
            continue;
          }
        }
        a.blockedFor = 0;
        const dx = next[0] - a.position[0],
          dy = next[1] - a.position[1],
          dist = Math.hypot(dx, dy),
          step = Math.min(dt, 0.05) * 0.085;
        if (Math.abs(dx) > 0.002) a.facing = dx < 0 ? -1 : 1;
        if (dist <= step) {
          a.position = [...next];
          a.path.shift();
          if (!a.path.length) a.nextBreak = this.time + 4 + this.random() * 7;
        } else {
          a.position[0] += (dx / dist) * step;
          a.position[1] += (dy / dist) * step;
        }
        a.frame = Math.floor(this.time * 12 + a.phase) % 8;
      } else a.frame = 2;
    }
  }
}
