import type { Texture } from "three";

/** Select a walk frame and mirror within its cell when the actor faces left. */
export function applyCharacterFrame(
  texture: Pick<Texture, "repeat" | "offset">,
  frame: number,
  row: number,
  facing: number,
  columns = 4,
) {
  const left = facing < 0;
  texture.repeat.set((left ? -1 : 1) / columns, 1 / 6);
  texture.offset.set((frame + (left ? 1 : 0)) / columns, 1 - (row + 1) / 6);
}

/** Sitting is cosmetic and only follows a real connected assignment at the desk. */
export function shouldSitAtDesk(
  online: boolean,
  status: string,
  moving: boolean,
  position: readonly number[],
  desk: readonly number[],
) {
  return (
    online &&
    ["running", "queued", "awaiting_approval"].includes(status) &&
    !moving &&
    Math.hypot(position[0] - desk[0], position[1] - desk[1]) < 0.012
  );
}
export function seatedFrame(
  progress: number,
  time: number,
  phase: number,
  typing: boolean,
) {
  if (progress < 0.5) return 8;
  if (progress < 1) return 9;
  return typing ? 10 + (Math.floor(time * 4 + phase) % 2) : 10;
}
