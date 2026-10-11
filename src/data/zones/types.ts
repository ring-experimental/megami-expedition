/** Zone data: everything FieldMode needs to build one area. three.js coords: x east, z south. */

export interface Circle { x: number; z: number; r: number }
export interface PropPlacement { name: string; x: number; z: number; rot?: number; scale?: number; y?: number; colliders?: Circle[]; steam?: boolean; light?: string; /** lamp lit only once this flag is set */ lightFlag?: string; /** steam vent height above ground */ steamY?: number; /** child node that turns slowly around Y (drive shaft rotor) */ spin?: string; /** placed only while flags allow */ afterFlag?: string; untilFlag?: string }
export interface ChestDef { id: string; x: number; z: number; rot: number; items: Record<string, number>; money: number; parts?: Record<string, number>; crystals?: Record<string, number>; /** opening sets this story flag (key items) */ flag?: string; flagText?: string; afterFlag?: string }
export interface SpawnDef {
  id: string; x: number; z: number; formation: string[]; wander: number;
  /** only while this flag is unset (e.g. a boss that leaves once beaten) */ untilFlag?: string;
  /** only once this flag is set */ afterFlag?: string;
  /** extra condition */ when?: () => boolean;
  /** never picks a fight */ passive?: boolean | (() => boolean);
}
/** Walking into a gate moves the party to `to`, arriving at that zone's gate `toGate`. */
export interface GateDef { id: string; x: number; z: number; r: number; to: string; toGate: string; label: string; /** gate stays shut until this flag is set */ needFlag?: string; lockedText?: string; /** gate doesn't exist until this flag */ afterFlag?: string }
export interface NpcDef { id: string; name: string; x: number; z: number; rot: number; model: string; color: string; y?: number; scale?: number; /** shown only once/while flags allow */ afterFlag?: string; untilFlag?: string; when?: () => boolean; /** no talk prompt (scenery) */ silent?: boolean }
/** Interactable spot (notice board, shop counter, workshop, story objects). */
export interface SpotDef { id: string; x: number; z: number; r: number; label: string; afterFlag?: string; untilFlag?: string; when?: () => boolean }
/** Frozen scenery creature (hushed monsters). */
export interface StatueDef { model: string; x: number; z: number; rot: number; scale?: number }
export interface ScatterDef { name: string; count: number; rMin: number; rMax: number; colR: number; sMin: number; sMax: number }

export interface TerrainDef {
  roads: [number, number][][];
  plazas: { x: number; z: number; r: number; rings?: number[] }[];
  /** rolling-hill amplitude (1 = plains) */
  hills: number;
  /** cliff ring: starts rising at edge[0], full height by edge[1] */
  edge: [number, number];
  seed: number;
  palette: { grassA: string; grassB: string; grassC: string; dirt: string; dirtB: string; stoneA: string; stoneB: string; cliff: string; cliffB: string; trim: string; grassTuft: string };
  /** grass tufts / flowers density (0 = bare ground) */
  grass: number;
  /** paved plaza tiles instead of grass everywhere inside this radius (towns) */
  paved?: number;
  /** interiors: walkable round rooms; outside them the ground rises into walls */
  rooms?: Circle[];
}

export interface ZoneDef {
  id: string;
  name: string;
  sub: string;
  /** walkable radius */
  radius: number;
  sky: { top: string; horizon: string; bottom: string; sun: string; sunDir: [number, number, number]; fog: string; fogNear: number; fogFar: number; hemiSky: string; hemiGround: string; hemi: number; sunColor: string; sunInt: number; mountain: string; cloud: string; motes: string };
  terrain: TerrainDef;
  start: { x: number; z: number; rot: number };
  props: PropPlacement[];
  chests: ChestDef[];
  spawns: SpawnDef[];
  scatter: ScatterDef[];
  gates: GateDef[];
  npcs: NpcDef[];
  spots: SpotDef[];
  airship?: boolean;
  statues?: StatueDef[];
  /** sky overrides while a flag is set (night, noon after the ending); the last match wins */
  skyVariants?: { flag: string; sky: Partial<ZoneDef['sky']> }[];
  /** minimap landmark squares */
  landmarks?: { x: number; z: number }[];
}
