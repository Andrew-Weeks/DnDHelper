import { client } from "./client";

export interface Combatant {
  id: number;
  name: string;
  modifier: number;
  roll: number | null;
  total: number | null;
  rank: number | null;
}

export interface Tracker {
  id: number;
  name: string;
  created_at: string;
  combatant_count: number;
  combatants?: Combatant[];
}

const base = "/api/initiative/trackers";

export const initiativeApi = {
  listTrackers: () => client.get<Tracker[]>(base).then((r) => r.data),
  createTracker: (name: string) => client.post<Tracker>(base, { name }).then((r) => r.data),
  getTracker: (id: number) => client.get<Tracker>(`${base}/${id}`).then((r) => r.data),
  deleteTracker: (id: number) => client.delete(`${base}/${id}`),

  addCombatant: (trackerId: number, name: string, modifier: number) =>
    client.post<Combatant>(`${base}/${trackerId}/combatants`, { name, modifier }).then((r) => r.data),
  deleteCombatant: (trackerId: number, combatantId: number) =>
    client.delete(`${base}/${trackerId}/combatants/${combatantId}`),

  rollAll: (trackerId: number) =>
    client.post<Tracker>(`${base}/${trackerId}/roll-all`).then((r) => r.data),
  rollCombatant: (trackerId: number, combatantId: number) =>
    client.post<Combatant>(`${base}/${trackerId}/combatants/${combatantId}/roll`).then((r) => r.data),
  customRoll: (trackerId: number, combatantId: number, roll: number) =>
    client.post<Combatant>(`${base}/${trackerId}/combatants/${combatantId}/custom-roll`, { roll }).then((r) => r.data),
  resetRolls: (trackerId: number) =>
    client.post<Tracker>(`${base}/${trackerId}/reset`).then((r) => r.data),
};
