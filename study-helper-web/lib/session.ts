"use client";

import { createUser, type User } from "@/lib/api";

/**
 * There is no auth yet. The backend identifies users by a numeric id, so
 * the browser keeps one: on first visit we create a throwaway user and
 * remember its id in localStorage. Clearing site data starts a fresh
 * learner — acceptable for a demo, and the thing real auth replaces.
 */
const STORAGE_KEY = "study-helper.user-id";

function readStoredId(): number | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const id = Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null; // private mode / storage disabled
  }
}

function storeId(id: number) {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(id));
  } catch {
    // fine: the session just won't survive a reload
  }
}

/** Returns the persisted user id, creating a user on the backend the
 * first time. In-flight calls share one promise so a double render (React
 * strict mode) can't create two users. */
let pending: Promise<number> | null = null;

export function getOrCreateUserId(targetCertification?: string): Promise<number> {
  const existing = readStoredId();
  if (existing !== null) return Promise.resolve(existing);
  if (pending) return pending;

  pending = createUser({
    email: `guest-${crypto.randomUUID()}@study-helper.local`,
    target_certification: targetCertification,
  })
    .then((user: User) => {
      storeId(user.id);
      return user.id;
    })
    .finally(() => {
      pending = null;
    });

  return pending;
}

export function clearSession() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing to clear
  }
}
