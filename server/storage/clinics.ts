import { db } from "../db";
import { and, asc, eq } from "drizzle-orm";
import { clinics, clinicAssignments, doctors, type Clinic, type InsertClinic, type ClinicAssignment, type InsertClinicAssignment, type Doctor } from "@shared/schema";

// Clinic operations
export async function getClinics(): Promise<Clinic[]> {
  return await db.select().from(clinics).orderBy(asc(clinics.name));
}

export async function getClinicsByDepartment(departmentId: number): Promise<Clinic[]> {
  return await db
    .select()
    .from(clinics)
    .where(eq(clinics.departmentId, departmentId))
    .orderBy(asc(clinics.name));
}

export async function getClinic(id: number): Promise<Clinic | undefined> {
  const [clinic] = await db.select().from(clinics).where(eq(clinics.id, id));
  return clinic || undefined;
}

export async function createClinic(clinic: InsertClinic): Promise<Clinic> {
  const [newClinic] = await db.insert(clinics).values(clinic).returning();
  return newClinic;
}

export async function updateClinic(id: number, clinic: Partial<InsertClinic>): Promise<Clinic> {
  const [updatedClinic] = await db
    .update(clinics)
    .set(clinic)
    .where(eq(clinics.id, id))
    .returning();
  return updatedClinic;
}

export async function deleteClinic(id: number): Promise<void> {
  // First delete all clinic assignments for this clinic
  await db.delete(clinicAssignments).where(eq(clinicAssignments.clinicId, id));
  // Then delete the clinic itself
  await db.delete(clinics).where(eq(clinics.id, id));
}

// Clinic assignment operations
export async function getClinicAssignments(): Promise<(ClinicAssignment & { doctor: Doctor; clinic: Clinic })[]> {
  return await db
    .select()
    .from(clinicAssignments)
    .leftJoin(doctors, eq(clinicAssignments.doctorId, doctors.id))
    .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
    .where(eq(clinicAssignments.isActive, true))
    .then(rows => rows.map(row => ({
      ...row.clinic_assignments,
      doctor: row.doctors!,
      clinic: row.clinics!
    })));
}

export async function getClinicAssignmentsByWeekday(weekday: number): Promise<(ClinicAssignment & { doctor: Doctor; clinic: Clinic })[]> {
  return await db
    .select()
    .from(clinicAssignments)
    .leftJoin(doctors, eq(clinicAssignments.doctorId, doctors.id))
    .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
    .where(and(
      eq(clinicAssignments.weekday, weekday),
      eq(clinicAssignments.isActive, true)
    ))
    .then(rows => rows.map(row => ({
      ...row.clinic_assignments,
      doctor: row.doctors!,
      clinic: row.clinics!
    })));
}

export async function getClinicAssignmentsByDepartment(departmentId: number): Promise<(ClinicAssignment & { doctor: Doctor; clinic: Clinic })[]> {
  return await db
    .select()
    .from(clinicAssignments)
    .leftJoin(doctors, eq(clinicAssignments.doctorId, doctors.id))
    .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
    .where(and(
      eq(clinics.departmentId, departmentId),
      eq(clinicAssignments.isActive, true)
    ))
    .then(rows => rows.map(row => ({
      ...row.clinic_assignments,
      doctor: row.doctors!,
      clinic: row.clinics!
    })));
}

export async function getClinicAssignmentsByWeekdayAndDepartment(weekday: number, departmentId: number): Promise<(ClinicAssignment & { doctor: Doctor; clinic: Clinic })[]> {
  return await db
    .select()
    .from(clinicAssignments)
    .leftJoin(doctors, eq(clinicAssignments.doctorId, doctors.id))
    .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
    .where(and(
      eq(clinicAssignments.weekday, weekday),
      eq(clinics.departmentId, departmentId),
      eq(clinicAssignments.isActive, true)
    ))
    .then(rows => rows.map(row => ({
      ...row.clinic_assignments,
      doctor: row.doctors!,
      clinic: row.clinics!
    })));
}

export async function createClinicAssignment(assignment: InsertClinicAssignment): Promise<ClinicAssignment> {
  const [newAssignment] = await db.insert(clinicAssignments).values(assignment).returning();
  return newAssignment;
}

export async function updateClinicAssignment(id: number, assignment: Partial<InsertClinicAssignment>): Promise<ClinicAssignment> {
  const [updatedAssignment] = await db
    .update(clinicAssignments)
    .set(assignment)
    .where(eq(clinicAssignments.id, id))
    .returning();
  return updatedAssignment;
}

export async function deleteClinicAssignment(id: number): Promise<void> {
  await db.delete(clinicAssignments).where(eq(clinicAssignments.id, id));
}

