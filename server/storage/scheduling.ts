import { db } from "../db";
import { format } from "date-fns";
import { and, asc, count, desc, eq, gte, lte } from "drizzle-orm";
import {
  doctors, departments, clinics, clinicAssignments, leaves, permissions, emergencyAssignments, examinationSlots, examinationAssignments,
  type Doctor, type Department, type Leave, type InsertLeave, type Permission, type InsertPermission,
  type EmergencyAssignment, type InsertEmergencyAssignment, type ExaminationSlot, type InsertExaminationSlot,
  type ExaminationAssignment, type InsertExaminationAssignment,
} from "@shared/schema";

// Leave operations
export async function getLeaves(): Promise<(Leave & { doctor: Doctor })[]> {
  return await db
    .select()
    .from(leaves)
    .leftJoin(doctors, eq(leaves.doctorId, doctors.id))
    .where(eq(leaves.isActive, true))
    .orderBy(desc(leaves.startDate))
    .then(rows => rows.map(row => ({
      ...row.leaves,
      doctor: row.doctors!
    })));
}

export async function getLeavesByDepartment(departmentId: number): Promise<(Leave & { doctor: Doctor })[]> {
  return await db
    .select()
    .from(leaves)
    .leftJoin(doctors, eq(leaves.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      eq(leaves.isActive, true)
    ))
    .orderBy(desc(leaves.startDate))
    .then(rows => rows.map(row => ({
      ...row.leaves,
      doctor: row.doctors!
    })));
}

export async function getActiveLeaves(): Promise<(Leave & { doctor: Doctor & { department: Department } })[]> {
  const today = new Date().toISOString().split('T')[0];
  return await db
    .select()
    .from(leaves)
    .leftJoin(doctors, eq(leaves.doctorId, doctors.id))
    .leftJoin(departments, eq(doctors.departmentId, departments.id))
    .where(and(
      eq(leaves.isActive, true),
      lte(leaves.startDate, today),
      gte(leaves.endDate, today)
    ))
    .orderBy(asc(doctors.name))
    .then(rows => rows.map(row => ({
      ...row.leaves,
      doctor: {
        ...row.doctors!,
        department: row.departments!
      }
    })));
}

export async function getActiveLeavesByDepartment(departmentId: number): Promise<(Leave & { doctor: Doctor })[]> {
  const today = new Date().toISOString().split('T')[0];
  return await db
    .select()
    .from(leaves)
    .leftJoin(doctors, eq(leaves.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      eq(leaves.isActive, true),
      lte(leaves.startDate, today),
      gte(leaves.endDate, today)
    ))
    .then(rows => rows.map(row => ({
      ...row.leaves,
      doctor: row.doctors!
    })));
}

export async function getLeavesByDoctor(doctorId: number): Promise<Leave[]> {
  return await db
    .select()
    .from(leaves)
    .where(and(
      eq(leaves.doctorId, doctorId),
      eq(leaves.isActive, true)
    ))
    .orderBy(desc(leaves.startDate));
}

export async function createLeave(leave: InsertLeave): Promise<Leave> {
  const [newLeave] = await db.insert(leaves).values(leave).returning();
  return newLeave;
}

export async function updateLeave(id: number, leave: Partial<InsertLeave>): Promise<Leave> {
  const [updatedLeave] = await db
    .update(leaves)
    .set(leave)
    .where(eq(leaves.id, id))
    .returning();
  return updatedLeave;
}

export async function deleteLeave(id: number): Promise<void> {
  await db.delete(leaves).where(eq(leaves.id, id));
}

// Permission operations
export async function getPermissions(): Promise<(Permission & { doctor: Doctor })[]> {
  return await db
    .select()
    .from(permissions)
    .leftJoin(doctors, eq(permissions.doctorId, doctors.id))
    .orderBy(desc(permissions.date))
    .then(rows => rows.map(row => ({
      ...row.permissions,
      doctor: row.doctors!
    })));
}

export async function getPermissionsByDepartment(departmentId: number): Promise<(Permission & { doctor: Doctor })[]> {
  return await db
    .select()
    .from(permissions)
    .leftJoin(doctors, eq(permissions.doctorId, doctors.id))
    .where(eq(doctors.departmentId, departmentId))
    .orderBy(desc(permissions.date))
    .then(rows => rows.map(row => ({
      ...row.permissions,
      doctor: row.doctors!
    })));
}

export async function getPermissionsByMonth(year: number, month: number): Promise<(Permission & { doctor: Doctor })[]> {
  const startDate = `${year}-${month.toString().padStart(2, '0')}-01`;
  const endDate = `${year}-${month.toString().padStart(2, '0')}-31`;
  
  return await db
    .select()
    .from(permissions)
    .leftJoin(doctors, eq(permissions.doctorId, doctors.id))
    .where(and(
      gte(permissions.date, startDate),
      lte(permissions.date, endDate)
    ))
    .orderBy(desc(permissions.date))
    .then(rows => rows.map(row => ({
      ...row.permissions,
      doctor: row.doctors!
    })));
}

export async function getPermissionsByMonthAndDepartment(year: number, month: number, departmentId: number): Promise<(Permission & { doctor: Doctor })[]> {
  const startDate = `${year}-${month.toString().padStart(2, '0')}-01`;
  const endDate = `${year}-${month.toString().padStart(2, '0')}-31`;
  
  return await db
    .select()
    .from(permissions)
    .leftJoin(doctors, eq(permissions.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      gte(permissions.date, startDate),
      lte(permissions.date, endDate)
    ))
    .orderBy(desc(permissions.date))
    .then(rows => rows.map(row => ({
      ...row.permissions,
      doctor: row.doctors!
    })));
}

export async function getPermissionsByDoctor(doctorId: number): Promise<Permission[]> {
  return await db
    .select()
    .from(permissions)
    .where(eq(permissions.doctorId, doctorId))
    .orderBy(desc(permissions.date));
}

export async function createPermission(permission: InsertPermission): Promise<Permission> {
  const [newPermission] = await db.insert(permissions).values(permission).returning();
  return newPermission;
}

export async function updatePermission(id: number, permission: Partial<InsertPermission>): Promise<Permission> {
  const [updatedPermission] = await db
    .update(permissions)
    .set(permission)
    .where(eq(permissions.id, id))
    .returning();
  return updatedPermission;
}

export async function deletePermission(id: number): Promise<void> {
  await db.delete(permissions).where(eq(permissions.id, id));
}

export async function clearAllPermissions(): Promise<void> {
  try {
    await db.delete(permissions);
  } catch (error) {
    console.error("Error clearing permissions:", error);
    throw new Error("Failed to clear permissions: " + (error instanceof Error ? error.message : "Unknown error"));
  }
}

// Emergency assignment operations
export async function getEmergencyAssignments(): Promise<(EmergencyAssignment & { doctor: Doctor })[]> {
  return await db
    .select()
    .from(emergencyAssignments)
    .leftJoin(doctors, eq(emergencyAssignments.doctorId, doctors.id))
    .orderBy(desc(emergencyAssignments.assignedDate), desc(emergencyAssignments.assignedTime))
    .then(rows => rows.map(row => ({
      ...row.emergency_assignments,
      doctor: row.doctors!
    })));
}

export async function getEmergencyAssignmentsByDepartment(departmentId: number): Promise<(EmergencyAssignment & { doctor: Doctor })[]> {
  return await db
    .select()
    .from(emergencyAssignments)
    .leftJoin(doctors, eq(emergencyAssignments.doctorId, doctors.id))
    .where(eq(doctors.departmentId, departmentId))
    .orderBy(desc(emergencyAssignments.assignedDate), desc(emergencyAssignments.assignedTime))
    .then(rows => rows.map(row => ({
      ...row.emergency_assignments,
      doctor: row.doctors!
    })));
}

export async function getEmergencyAssignmentsByMonth(year: number, month: number): Promise<(EmergencyAssignment & { doctor: Doctor })[]> {
  const startDate = `${year}-${month.toString().padStart(2, '0')}-01`;
  const endDate = `${year}-${month.toString().padStart(2, '0')}-31`;
  
  return await db
    .select()
    .from(emergencyAssignments)
    .leftJoin(doctors, eq(emergencyAssignments.doctorId, doctors.id))
    .where(and(
      gte(emergencyAssignments.assignedDate, startDate),
      lte(emergencyAssignments.assignedDate, endDate)
    ))
    .orderBy(desc(emergencyAssignments.assignedDate), desc(emergencyAssignments.assignedTime))
    .then(rows => rows.map(row => ({
      ...row.emergency_assignments,
      doctor: row.doctors!
    })));
}

export async function getEmergencyAssignmentsByMonthAndDepartment(year: number, month: number, departmentId: number): Promise<(EmergencyAssignment & { doctor: Doctor })[]> {
  const startDate = `${year}-${month.toString().padStart(2, '0')}-01`;
  const endDate = `${year}-${month.toString().padStart(2, '0')}-31`;
  
  return await db
    .select()
    .from(emergencyAssignments)
    .leftJoin(doctors, eq(emergencyAssignments.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      gte(emergencyAssignments.assignedDate, startDate),
      lte(emergencyAssignments.assignedDate, endDate)
    ))
    .orderBy(desc(emergencyAssignments.assignedDate), desc(emergencyAssignments.assignedTime))
    .then(rows => rows.map(row => ({
      ...row.emergency_assignments,
      doctor: row.doctors!
    })));
}

export async function getEmergencyAssignmentStats(): Promise<Array<{ doctor: Doctor; totalEmergencies: number }>> {
  const result = await db
    .select({
      doctor: doctors,
      totalEmergencies: count(emergencyAssignments.id)
    })
    .from(doctors)
    .leftJoin(emergencyAssignments, eq(doctors.id, emergencyAssignments.doctorId))
    .groupBy(doctors.id)
    .orderBy(desc(count(emergencyAssignments.id)), asc(doctors.name));
  
  return result.map(row => ({
    doctor: row.doctor,
    totalEmergencies: row.totalEmergencies
  }));
}

export async function getEmergencyAssignmentStatsByDepartment(departmentId: number): Promise<Array<{ doctor: Doctor; totalEmergencies: number }>> {
  const result = await db
    .select({
      doctor: doctors,
      totalEmergencies: count(emergencyAssignments.id)
    })
    .from(doctors)
    .leftJoin(emergencyAssignments, eq(doctors.id, emergencyAssignments.doctorId))
    .where(eq(doctors.departmentId, departmentId))
    .groupBy(doctors.id)
    .orderBy(desc(count(emergencyAssignments.id)), asc(doctors.name));
  
  return result.map(row => ({
    doctor: row.doctor,
    totalEmergencies: row.totalEmergencies
  }));
}

export async function createEmergencyAssignment(assignment: InsertEmergencyAssignment): Promise<EmergencyAssignment> {
  const [newAssignment] = await db.insert(emergencyAssignments).values(assignment).returning();
  return newAssignment;
}

export async function getNextEmergencyDoctor(): Promise<Doctor | undefined> {
  // Get all doctors with their emergency assignment counts
  const doctorsWithCounts = await db
    .select({
      doctor: doctors,
      assignmentCount: count(emergencyAssignments.id)
    })
    .from(doctors)
    .leftJoin(emergencyAssignments, eq(doctors.id, emergencyAssignments.doctorId))
    .groupBy(doctors.id)
    .orderBy(asc(count(emergencyAssignments.id)), asc(doctors.name));

  // Filter out doctors who are on leave today
  const today = new Date().toISOString().split('T')[0];
  const activeLeaves = await getActiveLeaves();
  const doctorsOnLeave = new Set(activeLeaves.map(leave => leave.doctorId));

  // Filter available doctors
  const availableDoctors = doctorsWithCounts.filter(
    item => !doctorsOnLeave.has(item.doctor.id)
  );

  if (availableDoctors.length === 0) return undefined;

  // Return the doctor with the least assignments (fair rotation)
  return availableDoctors[0].doctor;
}

export async function getNextEmergencyDoctorByDepartment(departmentId: number, skipDoctorIds: number[] = []): Promise<(Doctor & { currentClinic?: { id: number; name: string } }) | undefined> {
  const today = new Date();
  const currentWeekday = today.getDay();
  const currentTime = today.toTimeString().slice(0, 8); // HH:MM:SS
  const todayDate = format(today, 'yyyy-MM-dd');

  console.log(`[Emergency Storage] Department: ${departmentId}, Weekday: ${currentWeekday}, Time: ${currentTime}, Date: ${todayDate}`);

  // Build a clinic location map (for display only — does NOT gate eligibility)
  const todayAssignments = await db
    .select({ doctorId: clinicAssignments.doctorId, clinic: clinics })
    .from(clinicAssignments)
    .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
    .leftJoin(doctors, eq(clinicAssignments.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      eq(clinicAssignments.weekday, currentWeekday)
    ));

  const doctorClinicMap = new Map<number, { id: number; name: string; startTime: string }>();
  todayAssignments.forEach(assignment => {
    if (!assignment.clinic) return;
    const start = assignment.clinic.startTime;
    const end = assignment.clinic.endTime;
    const isActive = currentTime >= start && currentTime <= end;
    const existing = doctorClinicMap.get(assignment.doctorId);
    // Prefer active clinic, then next upcoming, then earliest
    if (!existing || isActive || (start > currentTime && (!existing.startTime || existing.startTime < currentTime || existing.startTime > start))) {
      doctorClinicMap.set(assignment.doctorId, { id: assignment.clinic.id, name: assignment.clinic.name, startTime: start });
    }
  });

  // Get ALL doctors in the department with their all-time emergency assignment count
  const doctorsWithCounts = await db
    .select({ doctor: doctors, assignmentCount: count(emergencyAssignments.id) })
    .from(doctors)
    .leftJoin(emergencyAssignments, eq(doctors.id, emergencyAssignments.doctorId))
    .where(eq(doctors.departmentId, departmentId))
    .groupBy(doctors.id)
    .orderBy(asc(count(emergencyAssignments.id)), asc(doctors.name));

  // Filter out doctors on leave today
  const activeLeaves = await getActiveLeavesByDepartment(departmentId);
  const doctorsOnLeave = new Set(activeLeaves.map(l => l.doctorId));

  // Filter out doctors with an active permission right now
  const todayPermissions = await db
    .select()
    .from(permissions)
    .leftJoin(doctors, eq(permissions.doctorId, doctors.id))
    .where(and(eq(doctors.departmentId, departmentId), eq(permissions.date, todayDate)));

  const doctorsWithActivePermissions = new Set<number>();
  todayPermissions.forEach(p => {
    if (p.permissions && currentTime >= p.permissions.startTime && currentTime <= p.permissions.endTime) {
      doctorsWithActivePermissions.add(p.permissions.doctorId);
    }
  });

  // Eligible = not on leave, not on active permission, not skipped
  const availableDoctors = doctorsWithCounts.filter(
    item => !doctorsOnLeave.has(item.doctor.id) &&
            !doctorsWithActivePermissions.has(item.doctor.id) &&
            !skipDoctorIds.includes(item.doctor.id)
  );

  console.log(`[Emergency Storage] Available doctors: ${availableDoctors.map(d => `${d.doctor.name}(${d.assignmentCount})`).join(', ')}`);

  if (availableDoctors.length === 0) return undefined;

  // Return doctor with fewest assignments; attach clinic location if available
  const selectedDoctor = availableDoctors[0].doctor;
  const clinicInfo = doctorClinicMap.get(selectedDoctor.id);
  const currentClinic = clinicInfo ? { id: clinicInfo.id, name: clinicInfo.name } : undefined;

  return { ...selectedDoctor, currentClinic };
}

export async function clearAllEmergencyAssignments(): Promise<void> {
  await db.delete(emergencyAssignments);
}

// Examination slot operations
export async function getExaminationSlots(): Promise<(ExaminationSlot & { assignments: (ExaminationAssignment & { doctor: Doctor })[] })[]> {
  const slots = await db
    .select()
    .from(examinationSlots)
    .where(eq(examinationSlots.isActive, true))
    .orderBy(asc(examinationSlots.weekday), asc(examinationSlots.startTime));

  const slotsWithAssignments = await Promise.all(
    slots.map(async (slot) => {
      const assignments = await db
        .select()
        .from(examinationAssignments)
        .leftJoin(doctors, eq(examinationAssignments.doctorId, doctors.id))
        .where(and(
          eq(examinationAssignments.slotId, slot.id),
          eq(examinationAssignments.isActive, true)
        ))
        .then(rows => rows.map(row => ({
          ...row.examination_assignments,
          doctor: row.doctors!
        })));

      return {
        ...slot,
        assignments
      };
    })
  );

  return slotsWithAssignments;
}

export async function getExaminationSlotsByDepartment(departmentId: number): Promise<(ExaminationSlot & { assignments: (ExaminationAssignment & { doctor: Doctor })[] })[]> {
  const slots = await db
    .select()
    .from(examinationSlots)
    .where(and(
      eq(examinationSlots.departmentId, departmentId),
      eq(examinationSlots.isActive, true)
    ))
    .orderBy(asc(examinationSlots.weekday), asc(examinationSlots.startTime));

  const slotsWithAssignments = await Promise.all(
    slots.map(async (slot) => {
      const assignments = await db
        .select()
        .from(examinationAssignments)
        .leftJoin(doctors, eq(examinationAssignments.doctorId, doctors.id))
        .where(and(
          eq(examinationAssignments.slotId, slot.id),
          eq(examinationAssignments.isActive, true)
        ))
        .then(rows => rows.map(row => ({
          ...row.examination_assignments,
          doctor: row.doctors!
        })));

      return {
        ...slot,
        assignments
      };
    })
  );

  return slotsWithAssignments;
}

export async function getExaminationSlotsByWeekday(weekday: number): Promise<(ExaminationSlot & { assignments: (ExaminationAssignment & { doctor: Doctor })[] })[]> {
  const slots = await db
    .select()
    .from(examinationSlots)
    .where(and(
      eq(examinationSlots.weekday, weekday),
      eq(examinationSlots.isActive, true)
    ))
    .orderBy(asc(examinationSlots.startTime));

  const slotsWithAssignments = await Promise.all(
    slots.map(async (slot) => {
      const assignments = await db
        .select()
        .from(examinationAssignments)
        .leftJoin(doctors, eq(examinationAssignments.doctorId, doctors.id))
        .where(and(
          eq(examinationAssignments.slotId, slot.id),
          eq(examinationAssignments.isActive, true)
        ))
        .then(rows => rows.map(row => ({
          ...row.examination_assignments,
          doctor: row.doctors!
        })));

      return {
        ...slot,
        assignments
      };
    })
  );

  return slotsWithAssignments;
}

export async function getExaminationSlotsByWeekdayAndDepartment(weekday: number, departmentId: number): Promise<(ExaminationSlot & { assignments: (ExaminationAssignment & { doctor: Doctor })[] })[]> {
  const slots = await db
    .select()
    .from(examinationSlots)
    .where(and(
      eq(examinationSlots.weekday, weekday),
      eq(examinationSlots.departmentId, departmentId),
      eq(examinationSlots.isActive, true)
    ))
    .orderBy(asc(examinationSlots.startTime));

  const slotsWithAssignments = await Promise.all(
    slots.map(async (slot) => {
      const assignments = await db
        .select()
        .from(examinationAssignments)
        .leftJoin(doctors, eq(examinationAssignments.doctorId, doctors.id))
        .where(and(
          eq(examinationAssignments.slotId, slot.id),
          eq(examinationAssignments.isActive, true)
        ))
        .then(rows => rows.map(row => ({
          ...row.examination_assignments,
          doctor: row.doctors!
        })));

      return {
        ...slot,
        assignments
      };
    })
  );

  return slotsWithAssignments;
}

export async function createExaminationSlot(slot: InsertExaminationSlot): Promise<ExaminationSlot> {
  const [newSlot] = await db.insert(examinationSlots).values(slot).returning();
  return newSlot;
}

export async function updateExaminationSlot(id: number, slot: Partial<InsertExaminationSlot>): Promise<ExaminationSlot> {
  const [updatedSlot] = await db
    .update(examinationSlots)
    .set(slot)
    .where(eq(examinationSlots.id, id))
    .returning();
  return updatedSlot;
}

export async function deleteExaminationSlot(id: number): Promise<void> {
  // First delete related assignments
  await db.delete(examinationAssignments).where(eq(examinationAssignments.slotId, id));
  // Then delete the slot
  await db.delete(examinationSlots).where(eq(examinationSlots.id, id));
}

// Examination assignment operations
export async function getExaminationAssignments(): Promise<(ExaminationAssignment & { doctor: Doctor; slot: ExaminationSlot })[]> {
  return await db
    .select()
    .from(examinationAssignments)
    .leftJoin(doctors, eq(examinationAssignments.doctorId, doctors.id))
    .leftJoin(examinationSlots, eq(examinationAssignments.slotId, examinationSlots.id))
    .where(eq(examinationAssignments.isActive, true))
    .then(rows => rows.map(row => ({
      ...row.examination_assignments,
      doctor: row.doctors!,
      slot: row.examination_slots!
    })));
}

export async function createExaminationAssignment(assignment: InsertExaminationAssignment): Promise<ExaminationAssignment> {
  const [newAssignment] = await db.insert(examinationAssignments).values(assignment).returning();
  return newAssignment;
}

export async function deleteExaminationAssignment(id: number): Promise<void> {
  await db.delete(examinationAssignments).where(eq(examinationAssignments.id, id));
}

