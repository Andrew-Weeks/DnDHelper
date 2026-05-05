import React, { useCallback, useEffect, useState } from "react";
import {
  View, Text, FlatList, TouchableOpacity, TextInput,
  StyleSheet, ActivityIndicator, Alert, Modal,
} from "react-native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { RouteProp } from "@react-navigation/native";
import { initiativeApi, Combatant, Tracker } from "../api/initiative";
import { RootStackParamList } from "../navigation/RootNavigator";

type Props = {
  navigation: NativeStackNavigationProp<RootStackParamList, "TrackerDetail">;
  route: RouteProp<RootStackParamList, "TrackerDetail">;
};

export default function TrackerDetailScreen({ navigation, route }: Props) {
  const { trackerId } = route.params;
  const [tracker, setTracker] = useState<Tracker | null>(null);
  const [newName, setNewName] = useState("");
  const [newModifier, setNewModifier] = useState("0");
  const [customRollId, setCustomRollId] = useState<number | null>(null);
  const [customRollVal, setCustomRollVal] = useState("");

  const load = useCallback(async () => {
    setTracker(await initiativeApi.getTracker(trackerId));
  }, [trackerId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (tracker) navigation.setOptions({ title: tracker.name });
  }, [tracker]);

  async function addCombatant() {
    if (!newName.trim()) return;
    await initiativeApi.addCombatant(trackerId, newName.trim(), parseInt(newModifier) || 0);
    setNewName(""); setNewModifier("0");
    load();
  }

  async function rollAll() { setTracker(await initiativeApi.rollAll(trackerId)); }
  async function reset() { setTracker(await initiativeApi.resetRolls(trackerId)); }

  async function rollOne(c: Combatant) {
    const updated = await initiativeApi.rollCombatant(trackerId, c.id);
    setTracker((prev) => prev ? { ...prev, combatants: prev.combatants!.map((x) => x.id === updated.id ? { ...x, ...updated } : x) } : prev);
  }

  async function submitCustomRoll() {
    if (customRollId == null) return;
    const val = parseInt(customRollVal);
    if (isNaN(val)) return;
    const updated = await initiativeApi.customRoll(trackerId, customRollId, val);
    setTracker((prev) => prev ? { ...prev, combatants: prev.combatants!.map((x) => x.id === updated.id ? { ...x, ...updated } : x) } : prev);
    setCustomRollId(null); setCustomRollVal("");
  }

  function confirmDelete(c: Combatant) {
    Alert.alert("Remove", `Remove ${c.name}?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Remove", style: "destructive", onPress: async () => { await initiativeApi.deleteCombatant(trackerId, c.id); load(); } },
    ]);
  }

  if (!tracker) return <ActivityIndicator style={{ flex: 1 }} color="#e94560" />;

  const combatants = tracker.combatants ?? [];

  return (
    <View style={styles.container}>
      <View style={styles.actions}>
        <TouchableOpacity style={styles.actionBtn} onPress={rollAll}>
          <Text style={styles.actionText}>Roll Unrolled</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionBtn, styles.resetBtn]} onPress={reset}>
          <Text style={styles.actionText}>Reset</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={combatants}
        keyExtractor={(c) => String(c.id)}
        renderItem={({ item: c, index }) => (
          <View style={styles.row}>
            <View style={styles.rankBadge}>
              <Text style={styles.rankText}>{c.roll != null ? index + 1 : "—"}</Text>
            </View>
            <View style={styles.rowInfo}>
              <Text style={styles.rowName}>{c.name}</Text>
              <Text style={styles.rowMod}>MOD {c.modifier >= 0 ? `+${c.modifier}` : c.modifier}</Text>
            </View>
            <View style={styles.rollInfo}>
              {c.roll != null ? (
                <Text style={[styles.total, c.roll === 20 && styles.nat20, c.roll === 1 && styles.nat1]}>
                  {c.total}
                </Text>
              ) : (
                <Text style={styles.unrolled}>—</Text>
              )}
            </View>
            <View style={styles.rowActions}>
              <TouchableOpacity onPress={() => rollOne(c)} style={styles.iconBtn}>
                <Text style={styles.iconText}>🎲</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setCustomRollId(c.id); setCustomRollVal(""); }} style={styles.iconBtn}>
                <Text style={styles.iconText}>✏️</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => confirmDelete(c)} style={styles.iconBtn}>
                <Text style={styles.iconText}>✕</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No combatants yet.</Text>}
      />

      <View style={styles.addRow}>
        <TextInput style={[styles.input, { flex: 2 }]} placeholder="Name" placeholderTextColor="#888" value={newName} onChangeText={setNewName} />
        <TextInput style={[styles.input, { flex: 1 }]} placeholder="MOD" placeholderTextColor="#888" keyboardType="numeric" value={newModifier} onChangeText={setNewModifier} />
        <TouchableOpacity style={styles.addBtn} onPress={addCombatant}>
          <Text style={styles.addBtnText}>Add</Text>
        </TouchableOpacity>
      </View>

      <Modal visible={customRollId != null} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>Enter Roll</Text>
            <TextInput
              style={styles.modalInput} keyboardType="numeric" autoFocus
              value={customRollVal} onChangeText={setCustomRollVal}
              onSubmitEditing={submitCustomRoll}
            />
            <View style={styles.modalBtns}>
              <TouchableOpacity onPress={() => setCustomRollId(null)} style={styles.modalCancel}>
                <Text style={{ color: "#888" }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={submitCustomRoll} style={styles.modalConfirm}>
                <Text style={{ color: "#fff", fontWeight: "bold" }}>OK</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#1a1a2e" },
  actions: { flexDirection: "row", padding: 12, gap: 8 },
  actionBtn: { flex: 1, backgroundColor: "#e94560", borderRadius: 8, padding: 12, alignItems: "center" },
  resetBtn: { backgroundColor: "#444" },
  actionText: { color: "#fff", fontWeight: "bold" },
  row: { flexDirection: "row", alignItems: "center", backgroundColor: "#16213e", marginHorizontal: 12, marginBottom: 6, borderRadius: 8, padding: 12 },
  rankBadge: { width: 32, height: 32, borderRadius: 16, backgroundColor: "#0f3460", justifyContent: "center", alignItems: "center", marginRight: 10 },
  rankText: { color: "#fff", fontWeight: "bold", fontSize: 12 },
  rowInfo: { flex: 1 },
  rowName: { color: "#fff", fontSize: 15, fontWeight: "600" },
  rowMod: { color: "#888", fontSize: 12 },
  rollInfo: { width: 40, alignItems: "center" },
  total: { color: "#fff", fontSize: 20, fontWeight: "bold" },
  nat20: { color: "#ffd700" },
  nat1: { color: "#e94560" },
  unrolled: { color: "#444", fontSize: 20 },
  rowActions: { flexDirection: "row", gap: 4 },
  iconBtn: { padding: 6 },
  iconText: { fontSize: 16 },
  addRow: { flexDirection: "row", padding: 12, gap: 8 },
  input: { backgroundColor: "#16213e", color: "#fff", borderRadius: 8, padding: 10, fontSize: 14 },
  addBtn: { backgroundColor: "#e94560", borderRadius: 8, padding: 10, justifyContent: "center" },
  addBtnText: { color: "#fff", fontWeight: "bold" },
  empty: { color: "#888", textAlign: "center", marginTop: 40 },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", alignItems: "center" },
  modalBox: { backgroundColor: "#16213e", borderRadius: 12, padding: 24, width: 240 },
  modalTitle: { color: "#fff", fontSize: 16, fontWeight: "bold", marginBottom: 12 },
  modalInput: { backgroundColor: "#0f3460", color: "#fff", borderRadius: 8, padding: 10, fontSize: 20, textAlign: "center", marginBottom: 16 },
  modalBtns: { flexDirection: "row", justifyContent: "flex-end", gap: 12 },
  modalCancel: { padding: 8 },
  modalConfirm: { backgroundColor: "#e94560", borderRadius: 8, padding: 8, paddingHorizontal: 16 },
});
