import { db } from "../db";
import { and, asc, eq } from "drizzle-orm";
import { departments, departmentMembers, doctors, clinics, users, type Department, type InsertDepartment, type DepartmentMember, type InsertDepartmentMember, type User, type Doctor, type Clinic } from "@shared/schema";

// Department operations
export async function getDepartments(): Promise<Department[]> {
  return await db.select().from(departments).orderBy(asc(departments.name));
}

export async function getDepartmentsByCenter(centerId: number): Promise<Department[]> {
  return await db.select().from(departments).where(eq(departments.centerId, centerId)).orderBy(asc(departments.name));
}

export async function getDepartment(id: number): Promise<Department | undefined> {
  const [department] = await db.select().from(departments).where(eq(departments.id, id));
  return department || undefined;
}

export async function createDepartment(department: InsertDepartment): Promise<Department> {
  const [newDepartment] = await db.insert(departments).values(department).returning();
  return newDepartment;
}

export async function updateDepartment(id: number, department: Partial<InsertDepartment>): Promise<Department> {
  const [updatedDepartment] = await db
    .update(departments)
    .set(department)
    .where(eq(departments.id, id))
    .returning();
  return updatedDepartment;
}

export async function deleteDepartment(id: number): Promise<void> {
  // Delete all department members first
  await db.delete(departmentMembers).where(eq(departmentMembers.departmentId, id));
  // Delete the department
  await db.delete(departments).where(eq(departments.id, id));
}

export async function getDepartmentData(id: number): Promise<{ doctors: Doctor[], clinics: Clinic[] }> {
  const [doctorsResult, clinicsResult] = await Promise.all([
    db.select().from(doctors).where(eq(doctors.departmentId, id)),
    db.select().from(clinics).where(eq(clinics.departmentId, id))
  ]);
  
  return {
    doctors: doctorsResult,
    clinics: clinicsResult
  };
}

export async function getUserDepartments(userId: string): Promise<Department[]> {
  const result = await db
    .select()
    .from(departmentMembers)
    .leftJoin(departments, eq(departmentMembers.departmentId, departments.id))
    .where(eq(departmentMembers.userId, userId));
  
  return result
    .filter(row => row.departments)
    .map(row => row.departments!);
}

export async function getDepartmentMembers(departmentId: number): Promise<(DepartmentMember & { user: User })[]> {
  return await db
    .select()
    .from(departmentMembers)
    .leftJoin(users, eq(departmentMembers.userId, users.id))
    .where(eq(departmentMembers.departmentId, departmentId))
    .then(rows => rows.map(row => ({
      ...row.department_members,
      user: row.users!
    })));
}

export async function addDepartmentMember(member: InsertDepartmentMember): Promise<DepartmentMember> {
  const [newMember] = await db.insert(departmentMembers).values(member).returning();
  return newMember;
}

export async function removeDepartmentMember(userId: string, departmentId: number): Promise<void> {
  await db.delete(departmentMembers).where(and(
    eq(departmentMembers.userId, userId),
    eq(departmentMembers.departmentId, departmentId)
  ));
}

export async function updateDepartmentMember(departmentId: number, userId: string, updates: Partial<InsertDepartmentMember>): Promise<void> {
  await db
    .update(departmentMembers)
    .set(updates)
    .where(and(
      eq(departmentMembers.userId, userId),
      eq(departmentMembers.departmentId, departmentId)
    ));
}

