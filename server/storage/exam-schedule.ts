import { db } from "../db";
import { and, asc, eq, gte, lte } from "drizzle-orm";
import { departments, examScheduleSlots, type ExamScheduleSlot, type InsertExamScheduleSlot } from "@shared/schema";

// ── Exam Schedule Slots ────────────────────────────────────────────────────

export async function getExamScheduleSlots(departmentId: number, startDate: string, endDate: string): Promise<ExamScheduleSlot[]> {
  return await db
    .select()
    .from(examScheduleSlots)
    .where(
      and(
        eq(examScheduleSlots.departmentId, departmentId),
        gte(examScheduleSlots.appointmentDate, startDate),
        lte(examScheduleSlots.appointmentDate, endDate)
      )
    )
    .orderBy(asc(examScheduleSlots.appointmentDate), asc(examScheduleSlots.slotTime));
}

export async function createExamScheduleSlot(slot: InsertExamScheduleSlot): Promise<ExamScheduleSlot> {
  const [created] = await db.insert(examScheduleSlots).values(slot).returning();
  return created;
}

export async function updateExamScheduleSlot(id: number, slot: Partial<InsertExamScheduleSlot>): Promise<ExamScheduleSlot> {
  const [updated] = await db
    .update(examScheduleSlots)
    .set(slot)
    .where(eq(examScheduleSlots.id, id))
    .returning();
  return updated;
}

export async function deleteExamScheduleSlot(id: number): Promise<void> {
  await db.delete(examScheduleSlots).where(eq(examScheduleSlots.id, id));
}

export async function setDepartmentCallCenterCode(departmentId: number, code: string): Promise<void> {
  await db
    .update(departments)
    .set({ callCenterCode: code })
    .where(eq(departments.id, departmentId));
}

export async function getDepartmentCallCenterCode(departmentId: number): Promise<string | null> {
  const [dept] = await db
    .select({ callCenterCode: departments.callCenterCode })
    .from(departments)
    .where(eq(departments.id, departmentId));
  return dept?.callCenterCode ?? null;
}
