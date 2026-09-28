import { db } from "../db";
import { and, count, eq, gte, lte } from "drizzle-orm";
import { doctors, leaves, emergencyAssignments } from "@shared/schema";
import { getActiveLeaves } from "./scheduling";

// Dashboard operations
export async function getDashboardStats(): Promise<{
  totalDoctors: number;
  availableToday: number;
  onLeave: number;
  emergencyCalls: number;
}> {
  const totalDoctors = await db.select({ count: count() }).from(doctors).then(r => r[0].count);
  
  const activeLeaves = await getActiveLeaves();
  const onLeave = activeLeaves.length;
  
  const availableToday = totalDoctors - onLeave;
  
  const today = new Date().toISOString().split('T')[0];
  const emergencyCalls = await db
    .select({ count: count() })
    .from(emergencyAssignments)
    .where(eq(emergencyAssignments.assignedDate, today))
    .then(r => r[0].count);

  return {
    totalDoctors,
    availableToday,
    onLeave,
    emergencyCalls
  };
}

export async function getDashboardStatsByDepartment(departmentId: number): Promise<{
  totalDoctors: number;
  availableToday: number;
  onLeave: number;
  emergencyCalls: number;
}> {
  // Get total doctors in this department
  const totalDoctors = await db
    .select({ count: count() })
    .from(doctors)
    .where(eq(doctors.departmentId, departmentId))
    .then(r => r[0].count);
  
  // Get doctors on leave from this department
  const today = new Date().toISOString().split('T')[0];
  const onLeave = await db
    .select({ count: count() })
    .from(leaves)
    .leftJoin(doctors, eq(leaves.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      eq(leaves.isActive, true),
      lte(leaves.startDate, today),
      gte(leaves.endDate, today)
    ))
    .then(r => r[0].count);
  
  const availableToday = totalDoctors - onLeave;
  
  // Get emergency assignments for this month for doctors in this department
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();
  const emergenciesThisMonth = await db
    .select({ count: count() })
    .from(emergencyAssignments)
    .leftJoin(doctors, eq(emergencyAssignments.doctorId, doctors.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      gte(emergencyAssignments.assignedDate, `${currentYear}-${currentMonth.toString().padStart(2, '0')}-01`)
    ))
    .then(r => r[0].count);

  return {
    totalDoctors,
    availableToday,
    onLeave,
    emergencyCalls: emergenciesThisMonth
  };
}

