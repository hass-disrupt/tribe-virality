/**
 * HeadViewer3D — interactive 3D head silhouette wrapping a real cortical brain
 * mesh sourced from Meta's TRIBE v2 demo. Hemispheres are vertex-colored by
 * interpolated TRIBE timeline activity using a direction-based ROI partition.
 *
 * GLB assets (FreeSurfer RAS frame: +X=right, +Y=anterior, +Z=superior) are
 * served from /models/. The viewer loads low-LOD pial + inflated meshes for
 * both hemispheres on mount, then upgrades to high-LOD in the background.
 */

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Maximize2, Sparkles, MoveHorizontal } from "lucide-react";
import type { TimelinePoint } from "../types";
import {
  BRAIN_BASE_COLOR,
  hotnessToRGB,
  getZone,
  zoneStrength,
  interpolateScores,
  ZONE_LABELS,
  ZONE_REGIONS,
  type ZoneKey,
} from "./brain/colormap";

const HEAD_GLB_URL = "/models/head.glb";

type Side = "L" | "R";
type Surface = "pial" | "inflated";
type Lod = "low" | "high";

const BRAIN_URLS: Record<Lod, Record<Surface, Record<Side, string>>> = {
  low: {
    pial: {
      L: "/models/brain-left-hemisphere.glb",
      R: "/models/brain-right-hemisphere.glb",
    },
    inflated: {
      L: "/models/brain-left-hemisphere-inflated.glb",
      R: "/models/brain-right-hemisphere-inflated.glb",
    },
  },
  high: {
    pial: {
      L: "/models/brain-left-hemisphere-high.glb",
      R: "/models/brain-right-hemisphere-high.glb",
    },
    // Meta's left-high-inflated.glb is a 2.5 KB stub on their CDN; fall back
    // to the low-LOD inflated mesh for the left hemisphere only.
    inflated: {
      L: "/models/brain-left-hemisphere-inflated.glb",
      R: "/models/brain-right-hemisphere-high-inflated.glb",
    },
  },
};

const ZONE_KEYS: ZoneKey[] = [
  "reward",
  "emotion",
  "attention",
  "novelty",
  "social_relevance",
];
const ZONE_INDEX: Record<ZoneKey, number> = {
  reward: 0,
  emotion: 1,
  attention: 2,
  novelty: 3,
  social_relevance: 4,
};

// FreeSurfer RAS → three.js convention. Swaps mesh-Y (anterior) with mesh-Z
// (superior) so the brain stands upright with its face pointing toward +Z.
// This is a reflection (det = -1); we render with DoubleSide to compensate.
const REORIENT = new THREE.Matrix4().set(
  1,
  0,
  0,
  0,
  0,
  0,
  1,
  0,
  0,
  1,
  0,
  0,
  0,
  0,
  0,
  1,
);

// Mesh-native units; brain spans ~140 across the midline so 30 ≈ 20% gap.
const EXPLODE_OFFSET_NATIVE = 30;
const EXPLODE_LERP = 0.18;

/** Sample hotnessToRGB at evenly-spaced stops to build a legend gradient
 *  that exactly matches what gets painted on the cortex. */
const LEGEND_GRADIENT = (() => {
  const toHex = (v: number) =>
    Math.round(Math.max(0, Math.min(1, v)) * 255)
      .toString(16)
      .padStart(2, "0");
  const stops = [0, 0.15, 0.35, 0.55, 0.75, 1].map((t) => {
    const [r, g, b] = hotnessToRGB(t);
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
})();

interface BrainMesh {
  mesh: THREE.Mesh;
  zones: Uint8Array;
  strengths: Float32Array;
  colorAttr: THREE.BufferAttribute;
}

interface HeadViewer3DProps {
  timeline: TimelinePoint[];
  playheadTime: number;
  className?: string;
}

export function HeadViewer3D({
  timeline,
  playheadTime,
  className,
}: HeadViewer3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showGuide, setShowGuide] = useState(false);
  const [inflated, setInflated] = useState(false);
  const [exploded, setExploded] = useState(false);

  const timeRef = useRef(playheadTime);
  const timelineRef = useRef(timeline);
  timeRef.current = playheadTime;
  timelineRef.current = timeline;

  const inflatedRef = useRef(inflated);
  const explodedRef = useRef(exploded);
  inflatedRef.current = inflated;
  explodedRef.current = exploded;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const w = container.clientWidth || 600;
    const h = container.clientHeight || 400;

    // ── renderer ──
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    // ── scene & camera ──
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, w / h, 0.05, 50);
    camera.position.set(0, 0.3, 4.6);
    camera.lookAt(0, 0, 0);

    // ── lighting ──
    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.05);
    keyLight.position.set(2.4, 3.0, 3.6);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xc8d4ff, 0.35);
    fillLight.position.set(-3.0, -1.0, 2.0);
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.45);
    rimLight.position.set(-1.0, 1.5, -3.0);
    scene.add(rimLight);

    // ── controls ──
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minDistance = 2.2;
    controls.maxDistance = 8.0;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.55;

    let idleTimer: number | undefined;
    const pauseAutoRotate = () => {
      controls.autoRotate = false;
      if (idleTimer) window.clearTimeout(idleTimer);
    };
    const scheduleResume = () => {
      if (idleTimer) window.clearTimeout(idleTimer);
      idleTimer = window.setTimeout(() => {
        controls.autoRotate = true;
      }, 2400);
    };
    controls.addEventListener("start", pauseAutoRotate);
    controls.addEventListener("end", scheduleResume);

    // ── brain group hierarchy ──
    // brainGroup (scaled, centered)
    //  ├ leftWrapper (animated explode offset)
    //  │   ├ leftPialGroup
    //  │   └ leftInflatedGroup
    //  └ rightWrapper
    //      ├ rightPialGroup
    //      └ rightInflatedGroup
    const brainGroup = new THREE.Group();
    const leftWrapper = new THREE.Group();
    const rightWrapper = new THREE.Group();
    const leftPialGroup = new THREE.Group();
    const leftInflatedGroup = new THREE.Group();
    const rightPialGroup = new THREE.Group();
    const rightInflatedGroup = new THREE.Group();
    leftWrapper.add(leftPialGroup, leftInflatedGroup);
    rightWrapper.add(rightPialGroup, rightInflatedGroup);
    brainGroup.add(leftWrapper, rightWrapper);
    leftInflatedGroup.visible = false;
    rightInflatedGroup.visible = false;
    scene.add(brainGroup);

    const meshesBySurface: Record<Surface, BrainMesh[]> = {
      pial: [],
      inflated: [],
    };

    let disposed = false;
    let highLoadStarted = false;
    let lowLoadCount = 0;
    let forceColorRefresh = false;

    const loader = new GLTFLoader();

    /**
     * Configure a freshly-loaded mesh: reorient RAS→three.js, recompute
     * normals, classify each vertex into one of 5 ROI zones using its unit
     * direction from the mesh centroid, attach a per-vertex color buffer,
     * and swap in our vertex-color-aware material.
     */
    function setupMesh(m: THREE.Mesh, side: Side): BrainMesh {
      const geo = m.geometry as THREE.BufferGeometry;
      geo.applyMatrix4(REORIENT);
      geo.computeVertexNormals();

      const pos = geo.attributes.position as THREE.BufferAttribute;

      // Centroid (vertex mean) — sufficient for direction-based ROI partition.
      let sx = 0;
      let sy = 0;
      let sz = 0;
      for (let i = 0; i < pos.count; i++) {
        sx += pos.getX(i);
        sy += pos.getY(i);
        sz += pos.getZ(i);
      }
      sx /= pos.count;
      sy /= pos.count;
      sz /= pos.count;

      // After REORIENT the mesh's local axes already match the colormap
      // convention: +X lateral, +Y superior, +Z anterior.
      const sideSign = side === "L" ? -1 : 1;
      const zones = new Uint8Array(pos.count);
      const strengths = new Float32Array(pos.count);
      for (let i = 0; i < pos.count; i++) {
        const dx = pos.getX(i) - sx;
        const dy = pos.getY(i) - sy;
        const dz = pos.getZ(i) - sz;
        const len = Math.hypot(dx, dy, dz) || 1;
        const nx = dx / len;
        const ny = dy / len;
        const nz = dz / len;
        const z = getZone(nx, ny, nz);
        zones[i] = ZONE_INDEX[z];
        strengths[i] = zoneStrength(z, nx, ny, nz, sideSign);
      }

      const colors = new Float32Array(pos.count * 3);
      for (let i = 0; i < pos.count; i++) {
        colors[i * 3] = BRAIN_BASE_COLOR[0];
        colors[i * 3 + 1] = BRAIN_BASE_COLOR[1];
        colors[i * 3 + 2] = BRAIN_BASE_COLOR[2];
      }
      const colorAttr = new THREE.BufferAttribute(colors, 3);
      geo.setAttribute("color", colorAttr);

      m.material = new THREE.MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.5,
        metalness: 0.0,
        side: THREE.DoubleSide,
      });

      return { mesh: m, zones, strengths, colorAttr };
    }

    function disposeGroupChildren(group: THREE.Group) {
      group.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if ((mesh as THREE.Mesh).isMesh) {
          mesh.geometry?.dispose();
          const mat = mesh.material;
          if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
          else (mat as THREE.Material | undefined)?.dispose();
        }
      });
      while (group.children.length > 0) group.remove(group.children[0]);
    }

    /** Remove all BrainMesh entries whose mesh sits under `target`. */
    function purgeStore(store: BrainMesh[], target: THREE.Object3D) {
      for (let i = store.length - 1; i >= 0; i--) {
        let p: THREE.Object3D | null = store[i].mesh.parent;
        while (p && p !== target) p = p.parent;
        if (p === target) store.splice(i, 1);
      }
    }

    function loadInto(
      url: string,
      parent: THREE.Group,
      side: Side,
      surface: Surface,
      onLoaded?: () => void,
    ) {
      loader.load(
        url,
        (gltf) => {
          if (disposed) return;
          gltf.scene.traverse((obj) => {
            const m = obj as THREE.Mesh;
            if ((m as THREE.Mesh).isMesh) {
              meshesBySurface[surface].push(setupMesh(m, side));
            }
          });
          parent.add(gltf.scene);
          onLoaded?.();
        },
        undefined,
        (err) => {
          console.warn(`[HeadViewer3D] failed to load ${url}`, err);
        },
      );
    }

    /** Replace the contents of a hemisphere group with a higher-LOD version. */
    function swapInto(
      url: string,
      parent: THREE.Group,
      store: BrainMesh[],
      side: Side,
    ) {
      loader.load(
        url,
        (gltf) => {
          if (disposed) return;
          purgeStore(store, parent);
          disposeGroupChildren(parent);
          gltf.scene.traverse((obj) => {
            const m = obj as THREE.Mesh;
            if ((m as THREE.Mesh).isMesh) {
              store.push(setupMesh(m, side));
            }
          });
          parent.add(gltf.scene);
          // Force one color refresh so the new mesh isn't stuck at base white.
          forceColorRefresh = true;
        },
        undefined,
        (err) => {
          console.warn(`[HeadViewer3D] high-LOD load failed for ${url}`, err);
        },
      );
    }

    /**
     * Center & scale the brain so it fits inside the head shell. Uses the
     * union bbox of every loaded surface (pial + inflated) so the inflated
     * mesh — which is ~25% larger across each axis — stays contained.
     */
    function fitBrain() {
      const box = new THREE.Box3();
      let hasContent = false;
      for (const g of [
        leftPialGroup,
        rightPialGroup,
        leftInflatedGroup,
        rightInflatedGroup,
      ]) {
        if (g.children.length > 0) {
          box.expandByObject(g);
          hasContent = true;
        }
      }
      if (!hasContent) return;

      const size = new THREE.Vector3();
      box.getSize(size);
      const center = new THREE.Vector3();
      box.getCenter(center);

      // Constrain by the longest extent (anterior-posterior on a brain).
      const maxDim = Math.max(size.x, size.y, size.z);
      const targetMax = 1.8;
      const scale = targetMax / Math.max(maxDim, 0.001);
      brainGroup.scale.setScalar(scale);
      // Lift the brain so its base sits roughly at ear level inside the head
      // shell rather than sagging toward the jaw.
      brainGroup.position.set(
        -center.x * scale,
        -center.y * scale + 0.62,
        -center.z * scale + 0.05,
      );
    }

    function maybeStartHighLOD() {
      if (highLoadStarted) return;
      if (lowLoadCount < 4) return;
      highLoadStarted = true;
      // Small delay so the first frames render before the heavy load begins.
      window.setTimeout(() => {
        if (disposed) return;
        swapInto(
          BRAIN_URLS.high.pial.L,
          leftPialGroup,
          meshesBySurface.pial,
          "L",
        );
        swapInto(
          BRAIN_URLS.high.pial.R,
          rightPialGroup,
          meshesBySurface.pial,
          "R",
        );
        // Left high-inflated is broken on Meta's CDN; skip and keep low-LOD.
        swapInto(
          BRAIN_URLS.high.inflated.R,
          rightInflatedGroup,
          meshesBySurface.inflated,
          "R",
        );
      }, 500);
    }

    const onLowLoaded = () => {
      lowLoadCount++;
      // Refit on every load so the inflated bbox (which is larger) is
      // included as soon as it's available.
      fitBrain();
      maybeStartHighLOD();
    };

    loadInto(BRAIN_URLS.low.pial.L, leftPialGroup, "L", "pial", onLowLoaded);
    loadInto(BRAIN_URLS.low.pial.R, rightPialGroup, "R", "pial", onLowLoaded);
    loadInto(
      BRAIN_URLS.low.inflated.L,
      leftInflatedGroup,
      "L",
      "inflated",
      onLowLoaded,
    );
    loadInto(
      BRAIN_URLS.low.inflated.R,
      rightInflatedGroup,
      "R",
      "inflated",
      onLowLoaded,
    );

    // ── load the head shell ──
    let headGroup: THREE.Group | null = null;
    loader.load(
      HEAD_GLB_URL,
      (gltf) => {
        if (disposed) return;
        headGroup = gltf.scene;

        const box = new THREE.Box3().setFromObject(headGroup);
        const size = new THREE.Vector3();
        box.getSize(size);
        const center = new THREE.Vector3();
        box.getCenter(center);
        const targetHeight = 2.6;
        const scale = targetHeight / Math.max(size.y, 0.0001);
        headGroup.scale.setScalar(scale);
        headGroup.position.sub(center.multiplyScalar(scale));

        headGroup.traverse((obj) => {
          const m = obj as THREE.Mesh;
          if ((m as THREE.Mesh).isMesh) {
            const material = new THREE.MeshStandardMaterial({
              color: 0x0a0a0a,
              transparent: true,
              opacity: 0.42,
              roughness: 1.0,
              metalness: 0.0,
              side: THREE.DoubleSide,
              depthWrite: false,
            });
            m.material = material;
            m.renderOrder = 2; // render after the brain so transparency composes correctly
          }
        });
        scene.add(headGroup);
      },
      undefined,
      (err) => {
        console.warn("[HeadViewer3D] failed to load head.glb", err);
      },
    );

    // ── animation loop ──
    let rafId: number;
    let lastT = -1;

    function updateColors(meshes: BrainMesh[], zoneHot: number[]) {
      for (const bm of meshes) {
        const arr = bm.colorAttr.array as Float32Array;
        const zones = bm.zones;
        const strengths = bm.strengths;
        for (let i = 0; i < zones.length; i++) {
          const h = zoneHot[zones[i]] * strengths[i];
          const [r, g, b] = hotnessToRGB(h);
          arr[i * 3] = r;
          arr[i * 3 + 1] = g;
          arr[i * 3 + 2] = b;
        }
        bm.colorAttr.needsUpdate = true;
      }
    }

    let lastSurface: Surface = "pial";

    function animate() {
      rafId = requestAnimationFrame(animate);

      // Visibility toggle for inflated/pial swap.
      const inf = inflatedRef.current;
      leftPialGroup.visible = !inf;
      rightPialGroup.visible = !inf;
      leftInflatedGroup.visible = inf;
      rightInflatedGroup.visible = inf;

      // Smooth lerp for explode offset.
      const target = explodedRef.current ? EXPLODE_OFFSET_NATIVE : 0;
      leftWrapper.position.x +=
        (-target - leftWrapper.position.x) * EXPLODE_LERP;
      rightWrapper.position.x +=
        (target - rightWrapper.position.x) * EXPLODE_LERP;

      // Per-frame coloring (throttled to ~25 Hz on playhead movement).
      const t = timeRef.current;
      const surface: Surface = inf ? "inflated" : "pial";
      const surfaceChanged = surface !== lastSurface;
      if (forceColorRefresh || surfaceChanged || Math.abs(t - lastT) > 0.04) {
        lastT = t;
        lastSurface = surface;
        forceColorRefresh = false;
        const scores = interpolateScores(timelineRef.current, t);
        // Hotness window. Real TRIBE outputs (with the current synthesized
        // baseline) cluster in 0–25, so map that range to [0,1] hotness.
        // When baseline_stats.json is recalibrated against measured videos
        // and scores spread closer to 0–100, widen `span` accordingly.
        const lo = 0;
        const span = 20;
        const zoneHot = ZONE_KEYS.map((k) =>
          Math.max(0, Math.min(1, (scores[k] - lo) / span)),
        );
        updateColors(meshesBySurface[surface], zoneHot);
      }

      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    // ── resize ──
    const ro = new ResizeObserver(() => {
      const w2 = container.clientWidth;
      const h2 = container.clientHeight;
      if (!w2 || !h2) return;
      camera.aspect = w2 / h2;
      camera.updateProjectionMatrix();
      renderer.setSize(w2, h2);
    });
    ro.observe(container);

    // ── cleanup ──
    return () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      if (idleTimer) window.clearTimeout(idleTimer);
      controls.removeEventListener("start", pauseAutoRotate);
      controls.removeEventListener("end", scheduleResume);
      controls.dispose();
      ro.disconnect();

      scene.traverse((obj) => {
        const m = obj as THREE.Mesh;
        if ((m as THREE.Mesh).isMesh) {
          m.geometry?.dispose();
          const mat = m.material;
          if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
          else (mat as THREE.Material | undefined)?.dispose();
        }
      });
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  const btnCls =
    "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs text-ink bg-black/50 hover:bg-black/70 border border-white/10 backdrop-blur-sm transition-colors";

  return (
    <div
      className={className}
      style={{ position: "relative", background: "#000" }}
    >
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {/* Top-left toggles */}
      <div className="absolute top-3 left-3 flex flex-col items-start gap-1.5">
        <button onClick={() => setShowGuide((v) => !v)} className={btnCls}>
          <Maximize2 className="w-3.5 h-3.5 -scale-x-100" />
          {showGuide ? "Hide Guide" : "Show Guide"}
        </button>
        <button onClick={() => setInflated((v) => !v)} className={btnCls}>
          <Sparkles className="w-3.5 h-3.5" />
          {inflated ? "Folded" : "Inflated"}
        </button>
        <button onClick={() => setExploded((v) => !v)} className={btnCls}>
          <MoveHorizontal className="w-3.5 h-3.5" />
          {exploded ? "Collapse" : "Explode"}
        </button>
      </div>

      {/* Activity legend */}
      <div className="absolute top-3 right-3 flex flex-col items-end gap-1 pointer-events-none">
        <div className="flex items-center justify-between w-32 text-[10px] text-ink-dim font-medium">
          <span>Low</span>
          <span>High</span>
        </div>
        <div
          className="h-1.5 w-32 rounded-full border border-white/10"
          style={{ background: LEGEND_GRADIENT }}
        />
        <span className="text-[10px] text-ink-dim mt-0.5">Activity</span>
      </div>

      {/* Guide panel */}
      {showGuide && (
        <div className="absolute bottom-3 left-3 max-w-[260px] rounded-lg border border-white/10 bg-black/70 backdrop-blur-md p-3 text-xs text-ink-dim">
          <div className="text-ink font-medium text-[11px] mb-1.5">
            Cortical regions
          </div>
          <ul className="flex flex-col gap-1">
            {(Object.keys(ZONE_LABELS) as ZoneKey[]).map((k) => (
              <li key={k} className="flex items-baseline gap-2">
                <span className="text-ink font-medium">{ZONE_LABELS[k]}</span>
                <span className="text-ink-dim text-[10px]">
                  {ZONE_REGIONS[k]}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-2 text-[10px] text-ink-dim leading-snug">
            Drag to rotate · scroll to zoom · idle to spin
          </div>
        </div>
      )}
    </div>
  );
}
