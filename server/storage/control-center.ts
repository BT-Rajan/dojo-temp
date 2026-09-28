import { db } from "../db";
import { and, eq } from "drizzle-orm";
import { departments, doctors, clinics, clinicAssignments, permissions, type Department, type ClinicAssignment, type Clinic, type Doctor, type Permission } from "@shared/schema";
import { getDepartments } from "./departments";

// Control Center operations
export async function getDepartmentsWithTodaysClinics(weekday: string): Promise<(Department & { todaysClinics: (ClinicAssignment & { clinic: Clinic; doctor: Doctor })[] })[]> {
  const departments = await getDepartments();
  
  // Convert weekday name to number (0 = Sunday, 1 = Monday, etc.)
  const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const weekdayNumber = weekdays.indexOf(weekday);
  
  if (weekdayNumber === -1) {
    throw new Error(`Invalid weekday: ${weekday}`);
  }
  
  const result = [];
  for (const department of departments) {
    // Get all clinic assignments for this department on the specified weekday
    const todaysClinics = await db
      .select()
      .from(clinicAssignments)
      .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
      .leftJoin(doctors, eq(clinicAssignments.doctorId, doctors.id))
      .where(and(
        eq(clinics.departmentId, department.id),
        eq(clinicAssignments.weekday, weekdayNumber),
        eq(clinicAssignments.isActive, true)
      ))
      .orderBy(clinics.name)
      .then(rows => rows.map(row => ({
        ...row.clinic_assignments,
        clinic: row.clinics!,
        doctor: row.doctors!
      })));

    result.push({
      ...department,
      todaysClinics
    });
  }
  
  return result;
}

export async function getPermissionsByDate(date: string): Promise<(Permission & { doctor: Doctor & { department: Department } })[]> {
  return await db
    .select()
    .from(permissions)
    .leftJoin(doctors, eq(permissions.doctorId, doctors.id))
    .leftJoin(departments, eq(doctors.departmentId, departments.id))
    .where(eq(permissions.date, date))
    .orderBy(doctors.name)
    .then(rows => rows.map(row => ({
      ...row.permissions,
      doctor: {
        ...row.doctors!,
        department: row.departments!
      }
    })));
}

