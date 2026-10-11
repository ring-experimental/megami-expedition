import type { ZoneDef } from './types';
import { PLAINS } from './plains';
import { STATION } from './station';
import { WORKS } from './works';
import { TOWER } from './tower';

export const ZONES: Record<string, ZoneDef> = {
  plains: PLAINS,
  pause_station: STATION,
  ashstack_works: WORKS,
  clocktower_interior: TOWER,
};
export * from './types';
