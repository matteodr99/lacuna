"use client";

import { ApiError, createUser, type User } from "@/lib/api";

/**
 * There is no auth yet. The backend identifies users by a numeric id, so
 * the browser keeps one: on first visit we create a throwaway user and
 * remember its id in localStorage. Clearing site data starts a fresh
 * learner — acceptable for a demo, and the thing real auth replaces.
 */
const STORAGE_KEY = "lacuna.user-id";

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
    email: `guest-${crypto.randomUUID()}@lacuna.local`,
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

/** True when the API says the user id we sent no longer exists. Distinct
 *  from the other 404 the quiz sees — "bank exhausted" — which must not be
 *  confused with this one, or a stale session reads as "you've answered
 *  everything". */
export function isMissingUser(error: unknown): boolean {
  return (
    error instanceof ApiError && error.status === 404 && /user not found/i.test(error.message)
  );
}

/**
 * Run `task` as the guest user, recovering if that user has vanished.
 *
 * The stored id is only as durable as the database behind it, and the dev
 * database gets recreated (no migrations). Before this, a browser that had
 * visited once kept sending an id that no longer existed and was stuck on
 * "User not found" for good. Now the first such answer discards the stored
 * id, creates a fresh guest and runs the task once more — history is lost,
 * which was already true, but the app keeps working.
 */
export async function withGuestUser<T>(
  task: (userId: number) => Promise<T>,
  certification?: string,
): Promise<T> {
  const userId = await getOrCreateUserId(certification);
  try {
    return await task(userId);
  } catch (error) {
    if (!isMissingUser(error)) throw error;
    clearSession();
    return task(await getOrCreateUserId(certification));
  }
}
