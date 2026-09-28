import { db } from "../db";
import { and, asc, eq } from "drizzle-orm";
import { users, centers, centerMembers, type Center, type InsertCenter, type CenterMember, type InsertCenterMember, type User } from "@shared/schema";

// Center operations
export async function getCenters(): Promise<Center[]> {
  return await db.select().from(centers).where(eq(centers.isActive, true)).orderBy(asc(centers.name));
}

export async function getCenter(id: number): Promise<Center | undefined> {
  const [center] = await db.select().from(centers).where(eq(centers.id, id));
  return center || undefined;
}

export async function createCenter(center: InsertCenter): Promise<Center> {
  const [newCenter] = await db.insert(centers).values(center).returning();
  return newCenter;
}

export async function updateCenter(id: number, center: Partial<InsertCenter>): Promise<Center> {
  const [updatedCenter] = await db.update(centers).set(center).where(eq(centers.id, id)).returning();
  return updatedCenter;
}

export async function deleteCenter(id: number): Promise<void> {
  await db.update(centers).set({ isActive: false }).where(eq(centers.id, id));
}

export async function getUserCenters(userId: string): Promise<Center[]> {
  const memberships = await db
    .select({ center: centers })
    .from(centerMembers)
    .innerJoin(centers, eq(centerMembers.centerId, centers.id))
    .where(and(eq(centerMembers.userId, userId), eq(centers.isActive, true)))
    .orderBy(asc(centers.name));
  return memberships.map(m => m.center);
}

export async function getCenterMembers(centerId: number): Promise<(CenterMember & { user: User })[]> {
  const rows = await db
    .select()
    .from(centerMembers)
    .innerJoin(users, eq(centerMembers.userId, users.id))
    .where(eq(centerMembers.centerId, centerId));
  return rows.map(row => ({
    ...row.center_members,
    user: row.users,
  }));
}

export async function addCenterMember(member: InsertCenterMember): Promise<CenterMember> {
  const [newMember] = await db.insert(centerMembers).values(member).returning();
  return newMember;
}

export async function removeCenterMember(userId: string, centerId: number): Promise<void> {
  await db.delete(centerMembers).where(
    and(eq(centerMembers.userId, userId), eq(centerMembers.centerId, centerId))
  );
}

