import { client, saveToken, clearToken } from "./client";

export interface AuthUser {
  id: number;
  username: string;
  role: string;
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const { data } = await client.post("/api/auth/login", { username, password });
  await saveToken(data.token);
  return data.user;
}

export async function logout() {
  await clearToken();
}
