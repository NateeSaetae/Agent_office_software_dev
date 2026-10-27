export type Point = [number, number];
export const DESKS: Point[] = [
  [0.3, 0.552],
  [0.515, 0.552],
  [0.725, 0.552],
  [0.32, 0.812],
  [0.525, 0.812],
  [0.755, 0.812],
];
export const BREAK_SPOTS: Point[] = [
  [0.887, 0.39],
  [0.93, 0.475],
  [0.205, 0.5],
  [0.52, 0.349],
  [0.27, 0.345],
  [0.55, 0.835],
  [0.62, 0.552],
  [0.418, 0.68],
];
// Coordinates align with the authored environment plate; feet never cross furniture.
const FURNITURE = [
  [0.0, 0.0, 0.255, 0.325],
  [0.34, 0.195, 0.615, 0.335],
  [0.775, 0.1, 0.945, 0.34],
  [0.221, 0.367, 0.401, 0.525],
  [0.433, 0.367, 0.606, 0.525],
  [0.636, 0.367, 0.82, 0.525],
  [0.225, 0.58, 0.412, 0.777],
  [0.438, 0.58, 0.631, 0.777],
  [0.648, 0.58, 0.837, 0.777],
  [0.0, 0.53, 0.19, 0.78],
  [0.86, 0.555, 1, 0.79],
];
export function isWalkable([x, y]: Point): boolean {
  return (
    x >= 0.065 &&
    x <= 0.945 &&
    y >= 0.337 &&
    y <= 0.845 &&
    !FURNITURE.some(([a, b, c, d]) => x >= a && x <= c && y >= b && y <= d)
  );
}
const COLS = 96,
  ROWS = 72;
export function findPath(start: Point, end: Point): Point[] {
  if (!isWalkable(end)) return [];
  const cell = ([x, y]: Point) =>
    [Math.round(x * COLS), Math.round(y * ROWS)] as Point;
  const a = cell(start),
    b = cell(end),
    key = ([x, y]: Point) => y * COLS + x;
  const open: Point[] = [a],
    cost = new Map([[key(a), 0]]),
    parent = new Map<number, Point>();
  const score = ([x, y]: Point) =>
    (cost.get(key([x, y])) ?? Infinity) +
    Math.abs(x - b[0]) +
    Math.abs(y - b[1]);
  for (let n = 0; open.length && n < 7000; n++) {
    open.sort((p, q) => score(p) - score(q));
    const p = open.shift()!;
    if (key(p) === key(b)) {
      const path: Point[] = [end];
      let current = p;
      while (key(current) !== key(a)) {
        path.unshift([current[0] / COLS, current[1] / ROWS]);
        current = parent.get(key(current))!;
      }
      return path;
    }
    for (const [dx, dy] of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ]) {
      const q: Point = [p[0] + dx, p[1] + dy],
        k = key(q),
        point: Point = [q[0] / COLS, q[1] / ROWS];
      if (!isWalkable(point)) continue;
      const c = cost.get(key(p))! + 1;
      if (c < (cost.get(k) ?? Infinity)) {
        cost.set(k, c);
        parent.set(k, p);
        if (!open.some((v) => key(v) === k)) open.push(q);
      }
    }
  }
  return [];
}
