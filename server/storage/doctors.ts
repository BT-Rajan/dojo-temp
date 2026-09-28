import { db } from "../db";
import { and, asc, eq } from "drizzle-orm";
import { doctors, departmentMembers, permissions, type Doctor, type InsertDoctor } from "@shared/schema";
import { getUser } from "./users";

// Doctor operations
export async function getDoctors(): Promise<Doctor[]> {
  return await db.select().from(doctors).orderBy(asc(doctors.name));
}

export async function getDoctor(id: number): Promise<Doctor | undefined> {
  const [doctor] = await db.select().from(doctors).where(eq(doctors.id, id));
  return doctor || undefined;
}

export async function createDoctor(doctor: InsertDoctor): Promise<Doctor> {
  const [newDoctor] = await db.insert(doctors).values(doctor).returning();
  return newDoctor;
}

export async function updateDoctor(id: number, doctor: Partial<InsertDoctor>): Promise<Doctor> {
  const [updatedDoctor] = await db
    .update(doctors)
    .set(doctor)
    .where(eq(doctors.id, id))
    .returning();
  return updatedDoctor;
}

export async function deleteDoctor(id: number): Promise<void> {
  await db.delete(doctors).where(eq(doctors.id, id));
}

export async function getDoctorsByDepartment(departmentId: number): Promise<Doctor[]> {
  return await db
    .select()
    .from(doctors)
    .where(eq(doctors.departmentId, departmentId))
    .orderBy(asc(doctors.name));
}

export async function canUserEditDepartment(userId: string, departmentId: number): Promise<boolean> {
  // Check if user is center head (can edit any department)
  const user = await getUser(userId);
  if (user?.isCenterHead) return true;

  // Check if user is department head or has edit permissions
  const [membership] = await db
    .select()
    .from(departmentMembers)
    .where(and(
      eq(departmentMembers.userId, userId),
      eq(departmentMembers.departmentId, departmentId),
      eq(departmentMembers.canEdit, true)
    ));
  
  return !!membership;
}

// Doctor authentication operations
export async function getDoctorByUsername(username: string): Promise<Doctor | undefined> {
  const [doctor] = await db.select().from(doctors).where(eq(doctors.username, username));
  return doctor;
}

export async function createDoctorAccount(doctorId: number, username: string, passwordHash: string): Promise<Doctor> {
  const [doctor] = await db
    .update(doctors)
    .set({ username, passwordHash })
    .where(eq(doctors.id, doctorId))
    .returning();
  return doctor;
}

export async function updateDoctorLogin(doctorId: number): Promise<void> {
  await db
    .update(doctors)
    .set({ lastLogin: new Date() })
    .where(eq(doctors.id, doctorId));
}

