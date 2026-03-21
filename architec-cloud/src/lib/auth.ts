import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { sessionCookieName } from "@/lib/config";
import { findSession, findUserById, readDb } from "@/lib/db";

export async function currentUser() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(sessionCookieName)?.value?.trim();
  if (!sessionId) {
    return null;
  }
  const db = await readDb();
  const session = findSession(db, sessionId);
  if (!session) {
    return null;
  }
  if (new Date(session.expiresAt).getTime() <= Date.now()) {
    return null;
  }
  return findUserById(db, session.userId) ?? null;
}

export async function requireUser() {
  const user = await currentUser();
  if (!user) {
    redirect("/login");
  }
  return user;
}

export async function requireAdmin() {
  const user = await requireUser();
  if (!user.isAdmin) {
    redirect("/account");
  }
  return user;
}
