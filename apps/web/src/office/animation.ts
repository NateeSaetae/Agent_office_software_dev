import type { Texture } from "three";

/** Select a walk frame and mirror within its cell when the actor faces left. */
export function applyCharacterFrame(
  texture: Pick<Texture, "repeat" | "offset">,
  frame: number,
  row: number,
  facing: number,
) {
  const left = facing < 0;
  texture.repeat.set(left ? -0.25 : 0.25, 1 / 6);
  texture.offset.set((frame + (left ? 1 : 0)) / 4, 1 - (row + 1) / 6);
}
