import React, { useCallback, useEffect, useState } from "react";
import {
  View, Text, FlatList, TouchableOpacity, TextInput,
  StyleSheet, ActivityIndicator, Alert,
} from "react-native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import { initiativeApi, Tracker } from "../api/initiative";
import { useAuth } from "../state/AuthContext";
import { RootStackParamList } from "../navigation/RootNavigator";

type Props = { navigation: NativeStackNavigationProp<RootStackParamList, "TrackerList"> };

export default function TrackerListScreen({ navigation }: Props) {
  const { signOut } = useAuth();
  const [trackers, setTrackers] = useState<Tracker[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setTrackers(await initiativeApi.listTrackers());
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function createTracker() {
    const tracker = await initiativeApi.createTracker(name.trim() || "Combat");
    setName("");
    navigation.navigate("TrackerDetail", { trackerId: tracker.id, trackerName: tracker.name });
  }

  function confirmDelete(tracker: Tracker) {
    Alert.alert("Delete", `Delete "${tracker.name}"?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive",
        onPress: async () => {
          await initiativeApi.deleteTracker(tracker.id);
          load();
        },
      },
    ]);
  }

  if (loading) return <ActivityIndicator style={{ flex: 1 }} color="#e94560" />;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Initiative Trackers</Text>
        <TouchableOpacity onPress={signOut}><Text style={styles.signOut}>Sign out</Text></TouchableOpacity>
      </View>
      <View style={styles.newRow}>
        <TextInput
          style={styles.input}
          placeholder="Combat name (optional)"
          placeholderTextColor="#888"
          value={name}
          onChangeText={setName}
        />
        <TouchableOpacity style={styles.createBtn} onPress={createTracker}>
          <Text style={styles.createBtnText}>+ New</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={trackers}
        keyExtractor={(t) => String(t.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => navigation.navigate("TrackerDetail", { trackerId: item.id, trackerName: item.name })}
            onLongPress={() => confirmDelete(item)}
          >
            <View>
              <Text style={styles.rowName}>{item.name}</Text>
              <Text style={styles.rowSub}>{item.combatant_count} combatants · long-press to delete</Text>
            </View>
            <Text style={styles.arrow}>›</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No trackers yet. Create one above.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#1a1a2e" },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, paddingTop: 56 },
  title: { fontSize: 22, fontWeight: "bold", color: "#fff" },
  signOut: { color: "#e94560", fontSize: 14 },
  newRow: { flexDirection: "row", paddingHorizontal: 16, paddingBottom: 12, gap: 8 },
  input: { flex: 1, backgroundColor: "#16213e", color: "#fff", borderRadius: 8, padding: 12, fontSize: 14 },
  createBtn: { backgroundColor: "#e94560", borderRadius: 8, padding: 12, justifyContent: "center" },
  createBtnText: { color: "#fff", fontWeight: "bold" },
  row: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    backgroundColor: "#16213e", marginHorizontal: 16, marginBottom: 8, borderRadius: 8, padding: 16,
  },
  rowName: { color: "#fff", fontSize: 16, fontWeight: "600" },
  rowSub: { color: "#888", fontSize: 12, marginTop: 2 },
  arrow: { color: "#888", fontSize: 22 },
  empty: { color: "#888", textAlign: "center", marginTop: 40, fontSize: 14 },
});
