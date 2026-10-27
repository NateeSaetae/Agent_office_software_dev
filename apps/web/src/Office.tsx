import {
  useMemo,
  useEffect,
  useRef,
  useState,
  Suspense,
  Component,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, useTexture } from "@react-three/drei";
import * as THREE from "three";
import { roles, useOffice } from "./store";
import { DESKS } from "./office/navigation";
import { OfficeSimulation } from "./office/simulation";
import {
  applyCharacterFrame,
  shouldSitAtDesk,
  seatedFrame,
} from "./office/animation";

function WorldCamera() {
  const { camera, size } = useThree();
  useEffect(() => {
    const c = camera as THREE.OrthographicCamera;
    c.left = -size.width / 2;
    c.right = size.width / 2;
    c.top = size.height / 2;
    c.bottom = -size.height / 2;
    c.zoom = 1;
    c.updateProjectionMatrix();
  }, [camera, size]);
  return null;
}
function Environment({ effects }: { effects: boolean }) {
  const texture = useTexture("/office/office-environment.png");
  const { size } = useThree();
  useEffect(() => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.magFilter = THREE.NearestFilter;
    texture.minFilter = THREE.LinearFilter;
  }, [texture]);
  return (
    <group>
      <mesh position={[0, 0, -20]}>
        <planeGeometry args={[size.width, size.height]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
      {effects && (
        <mesh position={[0, 0, -19]}>
          <planeGeometry args={[size.width, size.height]} />
          <meshBasicMaterial
            color="#ffdfad"
            transparent
            opacity={0.035}
            depthWrite={false}
          />
        </mesh>
      )}
    </group>
  );
}
function Character({
  index,
  simulation,
  reducedMotion,
}: {
  index: number;
  simulation: OfficeSimulation;
  reducedMotion: boolean;
}) {
  const atlas = useTexture("/office/characters-motion-v2.png");
  const { size } = useThree();
  const group = useRef<THREE.Group>(null),
    sprite = useRef<THREE.Sprite>(null),
    badge = useRef<HTMLSpanElement>(null);
  const agent = useOffice((s) => s.agents[index]);
  const activity = useOffice((s) => {
    const current = s.agents[index];
    const event = [...s.events]
      .reverse()
      .find(
        (e) =>
          e.agent_id === current.id &&
          (!current.task || e.task_id === current.task.id),
      );
    if (event?.type === "agent.testing") return "Testing";
    if (event?.type === "agent.working" || event?.tool === "workspace.write")
      return "Applying changes";
    return index === 5 ? "Reviewing" : "Thinking";
  });
  const selected = useOffice((s) => s.selected === roles[index].id);
  const online = useOffice((s) => s.online);
  const select = useOffice((s) => s.select);
  const map = useMemo(() => {
    const t = atlas.clone();
    t.repeat.set(1 / 12, 1 / 6);
    t.magFilter = THREE.NearestFilter;
    t.minFilter = THREE.NearestFilter;
    t.colorSpace = THREE.SRGBColorSpace;
    t.needsUpdate = true;
    return t;
  }, [atlas]);
  const alphaPixels = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = atlas.image.width;
    canvas.height = atlas.image.height;
    const context = canvas.getContext("2d")!;
    context.drawImage(atlas.image, 0, 0);
    return context.getImageData(0, 0, canvas.width, canvas.height).data;
  }, [atlas]);
  useEffect(() => () => map.dispose(), [map]);
  const nameTag = useRef<HTMLDivElement>(null);
  const height = Math.max(68, Math.min(122, size.height * 0.145));
  const sitProgress = useRef(0);
  const departProgress = useRef(1);
  useFrame((_, dt) => {
    const a = simulation.actors[index];
    if (!group.current || !sprite.current) return;
    const sitting = shouldSitAtDesk(
      online,
      a.status,
      a.moving,
      a.position,
      DESKS[index],
    );
    const previousSit = sitProgress.current;
    sitProgress.current = sitting ? Math.min(1, previousSit + dt / 0.38) : 0;
    if (!sitting && previousSit > 0) departProgress.current = 0;
    departProgress.current = Math.min(1, departProgress.current + dt / 0.25);
    const ease = (v: number) => v * v * (3 - 2 * v);
    const seated = sitting;
    const lift = seated ? ease(sitProgress.current) : 0;
    group.current.position.set(
      (a.position[0] - 0.5) * size.width,
      (0.5 - a.position[1]) * size.height +
        lift * height * (index >= 3 ? 0.23 : 0.075),
      a.position[1] * 10,
    );
    sprite.current.renderOrder = Math.round(a.position[1] * 1000);
    // Three.Sprite uses unsigned scale lengths; mirror the atlas UVs instead.
    const settle = seated ? 1.12 : 0.96 + 0.04 * ease(departProgress.current);
    sprite.current.scale.set(height * settle, height * settle, 1);
    const breathing = reducedMotion
      ? 0
      : Math.sin(simulation.time * 2 + a.phase) * (seated ? 0.35 : 0.65);
    sprite.current.position.y =
      (height * settle) / 2 +
      (a.moving
        ? (1 - Math.cos(simulation.time * Math.PI * 6 + a.phase)) * 0.45
        : breathing);
    const frame = seated
      ? seatedFrame(
          sitProgress.current,
          simulation.time,
          a.phase,
          a.status === "running" && !reducedMotion,
        )
      : a.frame;
    applyCharacterFrame(map, frame, index, seated ? 1 : a.facing, 12);
    if (nameTag.current) {
      const atDesk =
        Math.hypot(
          a.position[0] - DESKS[index][0],
          a.position[1] - DESKS[index][1],
        ) < 0.025;
      nameTag.current.style.visibility =
        atDesk && !selected ? "hidden" : "visible";
    }
    if (badge.current) {
      badge.current.dataset.motion = seated
        ? "seated"
        : a.moving
          ? "walking"
          : "standing";
      const label = !online
        ? "Offline"
        : a.status === "idle"
          ? a.moving
            ? "Walking on a break"
            : "Taking a break"
          : a.status === "awaiting_approval"
            ? "Needs approval"
            : a.moving
              ? "Heading to desk"
              : a.status === "queued"
                ? "Queued"
                : activity;
      if (badge.current.textContent !== label)
        badge.current.textContent = label;
    }
  });
  const running = online && agent.status === "running";
  return (
    <group ref={group}>
      <mesh
        position={[0, -1, -1]}
        rotation={[0, 0, 0]}
        scale={[height * 0.35, height * 0.08, 1]}
        renderOrder={0}
      >
        <circleGeometry args={[1, 24]} />
        <meshBasicMaterial
          color={selected ? "#55caff" : "#191f32"}
          transparent
          opacity={selected ? 0.5 : 0.27}
          depthWrite={false}
        />
      </mesh>
      {selected && (
        <mesh position={[0, 0, -0.5]} scale={[height * 0.4, height * 0.12, 1]}>
          <ringGeometry args={[0.85, 1, 32]} />
          <meshBasicMaterial
            color="#74d8ff"
            transparent
            opacity={0.85}
            depthTest={false}
          />
        </mesh>
      )}
      <sprite
        ref={sprite}
        onClick={(e) => {
          if (e.delta > 5 || !e.uv) return;
          const uv = e.uv.clone();
          map.updateMatrix();
          map.transformUv(uv);
          const x = Math.max(
              0,
              Math.min(
                atlas.image.width - 1,
                Math.floor(uv.x * atlas.image.width),
              ),
            ),
            y = Math.max(
              0,
              Math.min(
                atlas.image.height - 1,
                Math.floor(uv.y * atlas.image.height),
              ),
            );
          if (alphaPixels[(y * atlas.image.width + x) * 4 + 3] < 24) return;
          e.stopPropagation();
          select(roles[index].id);
        }}
        onPointerOver={() => (document.body.style.cursor = "pointer")}
        onPointerOut={() => (document.body.style.cursor = "auto")}
      >
        <spriteMaterial
          map={map}
          transparent
          alphaTest={0.08}
          depthTest={false}
          toneMapped={false}
        />
      </sprite>
      <Html
        position={[0, -13, 1]}
        center
        zIndexRange={[20, 10]}
        style={{ pointerEvents: "none" }}
      >
        <div
          ref={nameTag}
          className={"character-name " + (selected ? "selected" : "")}
          style={
            { "--character-accent": roles[index].color } as React.CSSProperties
          }
        >
          <i className={online ? agent.status : "offline"} />
          <strong>{roles[index].name}</strong>
          <span ref={badge} />
        </div>
      </Html>
      {(running || agent.status === "awaiting_approval") && (
        <Html
          position={[0, height + 7, 1]}
          center
          zIndexRange={[21, 11]}
          style={{ pointerEvents: "none" }}
        >
          <div className={"work-bubble " + (running ? "working" : "waiting")}>
            {agent.status === "awaiting_approval"
              ? "!"
              : activity === "Testing"
                ? "✓"
                : index === 5
                  ? "⌕"
                  : "···"}
          </div>
        </Html>
      )}
    </group>
  );
}
function Scene({
  effects,
  roaming,
  reducedMotion,
}: {
  effects: boolean;
  roaming: boolean;
  reducedMotion: boolean;
}) {
  const agents = useOffice((s) => s.agents),
    online = useOffice((s) => s.online);
  const simulation = useMemo(
    () => new OfficeSimulation(roles.map((a) => a.id)),
    [],
  );
  useEffect(
    () => simulation.sync(agents, online),
    [agents, online, simulation],
  );
  useFrame((_, dt) => simulation.update(dt, roaming, reducedMotion));
  const selectedId = useOffice((s) => s.selected);
  const { size } = useThree();
  return (
    <>
      <WorldCamera />
      <Environment effects={effects} />
      {roles.map((_, i) => (
        <Character
          key={i}
          index={i}
          simulation={simulation}
          reducedMotion={reducedMotion}
        />
      ))}
      {DESKS.map(([x, y], i) => (
        <Html
          key={i}
          position={[(x - 0.5) * size.width, (0.5 - y) * size.height - 14, -2]}
          center
          zIndexRange={[5, 0]}
          style={{ pointerEvents: "none" }}
        >
          <span
            className="desk-plaque"
            style={{
              visibility: selectedId === roles[i].id ? "hidden" : "visible",
            }}
          >
            {
              [
                "PLANNING",
                "FRONTEND",
                "BACKEND",
                "QA LAB",
                "DEVOPS",
                "CODE REVIEW",
              ][i]
            }
          </span>
        </Html>
      ))}
    </>
  );
}
class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="pixel-office-fallback">
        Your browser could not start the office scene.
        <br />
        Projects, tasks and agent logs remain available in the navigation.
      </div>
    ) : (
      this.props.children
    );
  }
}
export default function Office({
  effects = true,
  roaming = true,
}: {
  effects?: boolean;
  roaming?: boolean;
}) {
  const [reducedMotion, setReducedMotion] = useState(
    () => matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [viewport, setViewport] = useState({ width: 1600, height: 900 });
  const host = useRef<HTMLDivElement>(null),
    surface = useRef<HTMLDivElement>(null);
  const pan = useRef({ x: 0, y: 0 }),
    drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(
      null,
    );
  const aspect = 1672 / 941,
    scale = Math.max(viewport.width / 1672, viewport.height / 941);
  const width = 1672 * scale,
    height = 941 * scale;
  const place = () => {
    pan.current.x = Math.max(
      -(width - viewport.width) / 2,
      Math.min((width - viewport.width) / 2, pan.current.x),
    );
    pan.current.y = Math.max(
      -(height - viewport.height) / 2,
      Math.min((height - viewport.height) / 2, pan.current.y),
    );
    if (surface.current)
      surface.current.style.transform =
        "translate(" + pan.current.x + "px," + pan.current.y + "px)";
  };
  useEffect(() => {
    const q = matchMedia("(prefers-reduced-motion: reduce)"),
      change = () => setReducedMotion(q.matches);
    q.addEventListener("change", change);
    return () => q.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    if (!host.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setViewport({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      }),
    );
    observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  useEffect(place, [viewport.width, viewport.height, width, height]);
  return (
    <SceneBoundary>
      <div
        ref={host}
        className="office-canvas pixel-office"
        aria-label="Office scene. Drag to look around."
        onPointerDown={(e) => {
          if ((e.target as HTMLElement).tagName !== "CANVAS" || e.button !== 0)
            return;
          drag.current = {
            x: e.clientX,
            y: e.clientY,
            panX: pan.current.x,
            panY: pan.current.y,
          };
          (e.target as Element).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!drag.current) return;
          pan.current = {
            x: drag.current.panX + e.clientX - drag.current.x,
            y: drag.current.panY + e.clientY - drag.current.y,
          };
          place();
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      >
        <div
          ref={surface}
          className="office-room-surface"
          style={{
            width,
            height,
            left: (viewport.width - width) / 2,
            top: (viewport.height - height) / 2,
            aspectRatio: aspect,
          }}
        >
          <Canvas
            orthographic
            camera={{ position: [0, 0, 1000], near: 0.1, far: 2000, zoom: 1 }}
            dpr={[1, 2]}
            gl={{
              antialias: false,
              alpha: false,
              powerPreference: "high-performance",
            }}
          >
            <color attach="background" args={["#0a172a"]} />
            <Suspense
              fallback={
                <Html fullscreen>
                  <div className="pixel-office-loading">
                    <span />
                    <strong>Opening the office</strong>
                    <small>Loading pixel art &amp; teammates…</small>
                  </div>
                </Html>
              }
            >
              <Scene
                effects={effects}
                roaming={roaming}
                reducedMotion={reducedMotion}
              />
            </Suspense>
          </Canvas>
        </div>
        <div className="office-light-vignette" aria-hidden="true" />
      </div>
    </SceneBoundary>
  );
}
useTexture.preload("/office/office-environment.png");
useTexture.preload("/office/characters-motion-v2.png");
