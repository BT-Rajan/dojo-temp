import { db } from "../db";
import { asc, eq, inArray } from "drizzle-orm";
import { users, centerMembers, departments, departmentMembers, doctors, type User, type UpsertUser, type Doctor } from "@shared/schema";
import { getDepartmentsByCenter } from "./departments";

// User operations (for authentication)
export async function getUser(id: string): Promise<User | undefined> {
  const [user] = await db.select().from(users).where(eq(users.id, id));
  return user;
}

export async function getUserByUsername(username: string): Promise<User | undefined> {
  const [user] = await db.select().from(users).where(eq(users.username, username));
  return user;
}

export async function upsertUser(userData: UpsertUser): Promise<User> {
  // First try to find existing user by email to get the correct ID
  if (userData.email) {
    const existingUser = await db
      .select()
      .from(users)
      .where(eq(users.email, userData.email))
      .limit(1);
    
    if (existingUser.length > 0) {
      // Update existing user with new data but keep the original ID
      const [user] = await db
        .update(users)
        .set({
          ...userData,
          id: existingUser[0].id, // Preserve original ID
          updatedAt: new Date(),
        })
        .where(eq(users.id, existingUser[0].id))
        .returning();
      return user;
    }
  }
  
  // If no existing user found, insert new user
  const [user] = await db
    .insert(users)
    .values(userData)
    .onConflictDoUpdate({
      target: users.id,
      set: {
        ...userData,
        updatedAt: new Date(),
      },
    })
    .returning();
  return user;
}

export async function createLocalUser(userData: {
  username: string;
  passwordHash: string;
  firstName: string;
  lastName: string;
  email?: string;
  isCenterHead?: boolean;
}): Promise<User> {
  const [user] = await db
    .insert(users)
    .values({
      id: `local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      username: userData.username,
      passwordHash: userData.passwordHash,
      firstName: userData.firstName,
      lastName: userData.lastName,
      email: userData.email,
      isCenterHead: userData.isCenterHead || false,
      isLocalAccount: true,
    })
    .returning();
  return user;
}

export async function getAllUsers(): Promise<User[]> {
  return await db.select().from(users).orderBy(asc(users.firstName), asc(users.lastName));
}

export async function getUsersByCenter(centerId: number): Promise<User[]> {
  const members = await db
    .select({ user: users })
    .from(centerMembers)
    .innerJoin(users, eq(centerMembers.userId, users.id))
    .where(eq(centerMembers.centerId, centerId))
    .orderBy(asc(users.firstName), asc(users.lastName));
  return members.map(m => m.user);
}

export async function getDoctorsByCenter(centerId: number): Promise<Doctor[]> {
  const centerDepts = await getDepartmentsByCenter(centerId);
  const deptIds = centerDepts.map(d => d.id);
  if (deptIds.length === 0) return [];
  return await db
    .select()
    .from(doctors)
    .where(inArray(doctors.departmentId, deptIds))
    .orderBy(asc(doctors.name));
}

export async function updateUser(id: string, userData: Partial<UpsertUser>): Promise<User> {
  const [user] = await db
    .update(users)
    .set({ ...userData, updatedAt: new Date() })
    .where(eq(users.id, id))
    .returning();
  return user;
}

export async function updateUserPassword(id: string, passwordHash: string): Promise<void> {
  await db
    .update(users)
    .set({ passwordHash, updatedAt: new Date() })
    .where(eq(users.id, id));
}

export async function deleteUser(id: string): Promise<void> {
  // First remove user from all department head assignments
  await db
    .update(departments)
    .set({ headUserId: null })
    .where(eq(departments.headUserId, id));

  // Remove user from all department memberships
  await db
    .delete(departmentMembers)
    .where(eq(departmentMembers.userId, id));

  // Delete the user
  await db
    .delete(users)
    .where(eq(users.id, id));
}

