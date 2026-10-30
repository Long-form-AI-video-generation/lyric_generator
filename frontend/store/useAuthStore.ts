"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserProfile } from "@/lib/types";

type AuthState = {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: UserProfile) => void;
  setUser: (user: UserProfile) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null, isAuthenticated: false }),
    }),
    {
      name: "lyricvid-auth",
    }
  )
);
