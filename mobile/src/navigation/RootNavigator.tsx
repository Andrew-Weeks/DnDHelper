import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, View } from "react-native";
import { useAuth } from "../state/AuthContext";
import LoginScreen from "../screens/LoginScreen";
import TrackerListScreen from "../screens/TrackerListScreen";
import TrackerDetailScreen from "../screens/TrackerDetailScreen";

export type RootStackParamList = {
  Login: undefined;
  TrackerList: undefined;
  TrackerDetail: { trackerId: number; trackerName: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <View style={{ flex: 1, backgroundColor: "#1a1a2e", justifyContent: "center" }}><ActivityIndicator color="#e94560" /></View>;
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerStyle: { backgroundColor: "#16213e" }, headerTintColor: "#fff" }}>
        {user ? (
          <>
            <Stack.Screen name="TrackerList" component={TrackerListScreen} options={{ headerShown: false }} />
            <Stack.Screen name="TrackerDetail" component={TrackerDetailScreen} options={{ title: "Combat" }} />
          </>
        ) : (
          <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
