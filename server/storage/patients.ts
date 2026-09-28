import { db } from "../db";
import { and, asc, eq } from "drizzle-orm";
import { patients, type Patient, type InsertPatient } from "@shared/schema";

// Patient operations
export async function getPatients(): Promise<Patient[]> {
  return await db.select().from(patients).where(eq(patients.isActive, true)).orderBy(asc(patients.firstName), asc(patients.lastName));
}

export async function getPatientsByDepartment(departmentId: number): Promise<Patient[]> {
  return await db.select().from(patients).where(and(eq(patients.departmentId, departmentId), eq(patients.isActive, true))).orderBy(asc(patients.firstName), asc(patients.lastName));
}

export async function getPatient(id: number): Promise<Patient | undefined> {
  const [patient] = await db.select().from(patients).where(eq(patients.id, id));
  return patient;
}

export async function createPatient(patient: InsertPatient): Promise<Patient> {
  const [newPatient] = await db.insert(patients).values(patient).returning();
  return newPatient;
}

export async function updatePatient(id: number, patient: Partial<InsertPatient>): Promise<Patient> {
  const [updatedPatient] = await db
    .update(patients)
    .set({ ...patient, updatedAt: new Date() })
    .where(eq(patients.id, id))
    .returning();
  return updatedPatient;
}

export async function deletePatient(id: number): Promise<void> {
  await db.update(patients).set({ isActive: false }).where(eq(patients.id, id));
}

