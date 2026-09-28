import { format } from "date-fns";
import { db } from "../db";
import { and, eq, gte, inArray, lte } from "drizzle-orm";
import {
  doctors, patients, overtimeSessions, overtimeSlotEntries, overtimeProcedureLogs, overtimeSlotProcedureLogs,
  type Doctor, type OvertimeSession, type InsertOvertimeSession, type OvertimeSlotEntry, type InsertOvertimeSlotEntry,
  type OvertimeProcedureLog, type InsertOvertimeProcedureLog, type OvertimeSlotProcedureLog, type InsertOvertimeSlotProcedureLog,
} from "@shared/schema";
import { getDoctor, getDoctorsByDepartment } from "./doctors";

// Overtime operations
export async function getOvertimeSessions(departmentId: number, date?: string): Promise<(OvertimeSession & { doctor: Doctor | null })[]> {
  const conditions = [eq(overtimeSessions.departmentId, departmentId)];
  if (date) conditions.push(eq(overtimeSessions.sessionDate, date));
  const rows = await db.select().from(overtimeSessions).where(and(...conditions)).orderBy(overtimeSessions.sessionDate, overtimeSessions.clinicName);
  return Promise.all(rows.map(async (s) => {
    const doctor = s.doctorId ? (await db.select().from(doctors).where(eq(doctors.id, s.doctorId)))[0] ?? null : null;
    return { ...s, doctor };
  }));
}

export async function getOvertimeSessionsByDateRange(departmentId: number, startDate: string, endDate: string): Promise<(OvertimeSession & { doctor: Doctor | null })[]> {
  const rows = await db.select().from(overtimeSessions)
    .where(and(eq(overtimeSessions.departmentId, departmentId), gte(overtimeSessions.sessionDate, startDate), lte(overtimeSessions.sessionDate, endDate)))
    .orderBy(overtimeSessions.sessionDate, overtimeSessions.clinicName);
  return Promise.all(rows.map(async (s) => {
    const doctor = s.doctorId ? (await db.select().from(doctors).where(eq(doctors.id, s.doctorId)))[0] ?? null : null;
    return { ...s, doctor };
  }));
}

export async function getOvertimeSession(id: number): Promise<OvertimeSession | undefined> {
  const [row] = await db.select().from(overtimeSessions).where(eq(overtimeSessions.id, id));
  return row;
}

export async function createOvertimeSession(session: InsertOvertimeSession): Promise<OvertimeSession> {
  const [row] = await db.insert(overtimeSessions).values(session).returning();
  return row;
}

export async function updateOvertimeSession(id: number, session: Partial<InsertOvertimeSession>): Promise<OvertimeSession> {
  const [row] = await db.update(overtimeSessions).set(session).where(eq(overtimeSessions.id, id)).returning();
  return row;
}

export async function deleteOvertimeSession(id: number): Promise<void> {
  await db.delete(overtimeSlotEntries).where(eq(overtimeSlotEntries.sessionId, id));
  await db.delete(overtimeSessions).where(eq(overtimeSessions.id, id));
}

export async function getOvertimeSlotEntries(sessionId: number): Promise<OvertimeSlotEntry[]> {
  return db.select().from(overtimeSlotEntries).where(eq(overtimeSlotEntries.sessionId, sessionId)).orderBy(overtimeSlotEntries.timeSlot);
}

export async function createOvertimeSlotEntry(entry: InsertOvertimeSlotEntry): Promise<OvertimeSlotEntry> {
  const [row] = await db.insert(overtimeSlotEntries).values(entry).returning();
  return row;
}

export async function updateOvertimeSlotEntry(id: number, entry: Partial<InsertOvertimeSlotEntry>): Promise<OvertimeSlotEntry> {
  const [row] = await db.update(overtimeSlotEntries).set(entry).where(eq(overtimeSlotEntries.id, id)).returning();
  return row;
}

export async function deleteOvertimeSlotEntry(id: number): Promise<void> {
  await db.delete(overtimeSlotEntries).where(eq(overtimeSlotEntries.id, id));
}

// Per-patient (slot) procedure log operations
export async function getOvertimeSlotProcedureLog(slotEntryId: number): Promise<OvertimeSlotProcedureLog | undefined> {
  const [row] = await db.select().from(overtimeSlotProcedureLogs).where(eq(overtimeSlotProcedureLogs.slotEntryId, slotEntryId));
  return row;
}

export async function getOvertimeSlotProcedureLogsBySession(sessionId: number): Promise<OvertimeSlotProcedureLog[]> {
  const entries = await db.select().from(overtimeSlotEntries).where(eq(overtimeSlotEntries.sessionId, sessionId));
  if (entries.length === 0) return [];
  const entryIds = entries.map(e => e.id);
  return db.select().from(overtimeSlotProcedureLogs).where(inArray(overtimeSlotProcedureLogs.slotEntryId, entryIds));
}

export async function upsertOvertimeSlotProcedureLog(data: InsertOvertimeSlotProcedureLog): Promise<OvertimeSlotProcedureLog> {
  const existing = await getOvertimeSlotProcedureLog(data.slotEntryId);
  if (existing) {
    const [row] = await db.update(overtimeSlotProcedureLogs)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(overtimeSlotProcedureLogs.slotEntryId, data.slotEntryId))
      .returning();
    return row;
  }
  const [row] = await db.insert(overtimeSlotProcedureLogs).values(data).returning();
  return row;
}

export async function copyWeekOvertimeSessions(departmentId: number, fromStart: string, fromEnd: string): Promise<{ created: number; skipped: number }> {
  const sourceSessions = await getOvertimeSessionsByDateRange(departmentId, fromStart, fromEnd);
  const toStart = new Date(fromStart);
  toStart.setDate(toStart.getDate() + 7);
  const toEnd = new Date(fromEnd);
  toEnd.setDate(toEnd.getDate() + 7);
  const toStartStr = format(toStart, "yyyy-MM-dd");
  const toEndStr = format(toEnd, "yyyy-MM-dd");
  const targetSessions = await getOvertimeSessionsByDateRange(departmentId, toStartStr, toEndStr);

  let created = 0;
  let skipped = 0;

  for (const s of sourceSessions) {
    const srcDate = new Date(s.sessionDate);
    srcDate.setDate(srcDate.getDate() + 7);
    const targetDate = format(srcDate, "yyyy-MM-dd");
    const alreadyExists = targetSessions.some(t => t.clinicName === s.clinicName && t.sessionDate === targetDate);
    if (alreadyExists) { skipped++; continue; }
    await createOvertimeSession({
      departmentId: s.departmentId,
      clinicName: s.clinicName,
      doctorId: s.doctorId,
      sessionDate: targetDate,
      isOpen: true,
      notes: s.notes,
    });
    created++;
  }
  return { created, skipped };
}

// Overtime Procedure Log operations (per-session, legacy)
export async function getOvertimeProcedureLogBySession(sessionId: number): Promise<OvertimeProcedureLog | undefined> {
  const [row] = await db.select().from(overtimeProcedureLogs).where(eq(overtimeProcedureLogs.sessionId, sessionId));
  return row;
}

export async function upsertOvertimeProcedureLog(data: InsertOvertimeProcedureLog): Promise<OvertimeProcedureLog> {
  const existing = await getOvertimeProcedureLogBySession(data.sessionId);
  if (existing) {
    const [row] = await db.update(overtimeProcedureLogs)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(overtimeProcedureLogs.sessionId, data.sessionId))
      .returning();
    return row;
  }
  const [row] = await db.insert(overtimeProcedureLogs).values(data).returning();
  return row;
}

export async function getAggregatedOvertimeProcedureStats(departmentId: number, startDate: string, endDate: string, doctorId?: number): Promise<{
  perDoctor: Array<{
    doctor: Doctor;
    treatedPatients: number;
    sessionCount: number;
    procedureTotals: Record<string, number>;
  }>;
  departmentTotals: {
    treatedPatients: number;
    sessionCount: number;
    procedureTotals: Record<string, number>;
  };
  dailyBreakdown: Array<{
    date: string;
    treatedPatients: number;
    totalProcedures: number;
  }>;
}> {
  const procedureKeys = [
    'alginatePreparation', 'crownPreparation', 'bridgePreparation', 'finalImpression',
    'tempCementation', 'cementAccBb', 'cementPorcelainCb', 'metalCrownCb', 'porcelainCb',
    'postPreparation', 'postCanal', 'compositeFilling', 'amalgamFilling',
    'removableProstho', 'removableProsthoRepair', 'cbRemovalPostCore',
    'orthoAppliances', 'buckleAppointment', 'implantUnits', 'tryIn', 'miscellaneous', 'examination'
  ];

  // === Query 1: Per-patient slot procedure logs ===
  const slotConditions = [
    eq(overtimeSessions.departmentId, departmentId),
    gte(overtimeSessions.sessionDate, startDate),
    lte(overtimeSessions.sessionDate, endDate),
  ];
  if (doctorId) slotConditions.push(eq(overtimeSessions.doctorId, doctorId));

  const slotRows = await db
    .select({
      log: overtimeSlotProcedureLogs,
      sessionDate: overtimeSessions.sessionDate,
      sessionId: overtimeSessions.id,
      sessionDoctorId: overtimeSessions.doctorId,
    })
    .from(overtimeSlotProcedureLogs)
    .innerJoin(overtimeSlotEntries, eq(overtimeSlotProcedureLogs.slotEntryId, overtimeSlotEntries.id))
    .innerJoin(overtimeSessions, eq(overtimeSlotEntries.sessionId, overtimeSessions.id))
    .where(and(...slotConditions));

  // === Query 2: Per-session procedure logs ===
  const sessionConditions = [
    eq(overtimeProcedureLogs.departmentId, departmentId),
    gte(overtimeProcedureLogs.sessionDate, startDate),
    lte(overtimeProcedureLogs.sessionDate, endDate),
  ];
  if (doctorId) sessionConditions.push(eq(overtimeProcedureLogs.doctorId, doctorId));

  const sessionLogs = await db
    .select()
    .from(overtimeProcedureLogs)
    .where(and(...sessionConditions));

  const departmentDoctors = doctorId
    ? [await getDoctor(doctorId)].filter(Boolean) as Doctor[]
    : await getDoctorsByDepartment(departmentId);

  const doctorMap = new Map<number, Doctor>();
  departmentDoctors.forEach(d => doctorMap.set(d.id, d));

  const perDoctorMap = new Map<number, { treatedPatients: number; sessionIds: Set<number>; procedureTotals: Record<string, number> }>();
  const dailyMap = new Map<string, { treatedPatients: number; totalProcedures: number }>();
  const departmentTotals = { treatedPatients: 0, sessionCount: 0, procedureTotals: {} as Record<string, number> };
  const allSessionIds = new Set<number>();
  procedureKeys.forEach(k => departmentTotals.procedureTotals[k] = 0);

  const ensureDoc = (dId: number) => {
    if (!perDoctorMap.has(dId)) {
      const t: Record<string, number> = {};
      procedureKeys.forEach(k => t[k] = 0);
      perDoctorMap.set(dId, { treatedPatients: 0, sessionIds: new Set(), procedureTotals: t });
    }
    return perDoctorMap.get(dId)!;
  };

  const addDay = (dateStr: string, patients: number, procs: number) => {
    if (!dailyMap.has(dateStr)) dailyMap.set(dateStr, { treatedPatients: 0, totalProcedures: 0 });
    const d = dailyMap.get(dateStr)!;
    d.treatedPatients += patients;
    d.totalProcedures += procs;
  };

  // Aggregate slot logs — each row = 1 patient
  for (const row of slotRows) {
    allSessionIds.add(row.sessionId);
    departmentTotals.treatedPatients += 1;
    let dayProcs = 0;
    for (const key of procedureKeys) {
      const val = (row.log as any)[key] || 0;
      departmentTotals.procedureTotals[key] += val;
      dayProcs += val;
    }
    addDay(row.sessionDate, 1, dayProcs);

    const dId = row.sessionDoctorId;
    if (dId && doctorMap.has(dId)) {
      const ds = ensureDoc(dId);
      ds.treatedPatients += 1;
      ds.sessionIds.add(row.sessionId);
      for (const key of procedureKeys) {
        ds.procedureTotals[key] += (row.log as any)[key] || 0;
      }
    }
  }

  // Aggregate session-level logs — each row = 1 session
  for (const log of sessionLogs) {
    allSessionIds.add(log.sessionId);
    const treated = log.treatedPatients || 0;
    departmentTotals.treatedPatients += treated;
    let dayProcs = 0;
    for (const key of procedureKeys) {
      const val = (log as any)[key] || 0;
      departmentTotals.procedureTotals[key] += val;
      dayProcs += val;
    }
    addDay(log.sessionDate, treated, dayProcs);

    if (doctorMap.has(log.doctorId)) {
      const ds = ensureDoc(log.doctorId);
      ds.treatedPatients += treated;
      ds.sessionIds.add(log.sessionId);
      for (const key of procedureKeys) {
        ds.procedureTotals[key] += (log as any)[key] || 0;
      }
    }
  }

  departmentTotals.sessionCount = allSessionIds.size;

  const perDoctor = Array.from(perDoctorMap.entries())
    .filter(([id]) => doctorMap.has(id))
    .map(([id, stats]) => ({
      doctor: doctorMap.get(id)!,
      treatedPatients: stats.treatedPatients,
      sessionCount: stats.sessionIds.size,
      procedureTotals: stats.procedureTotals,
    }));

  for (const doc of departmentDoctors) {
    if (!perDoctorMap.has(doc.id)) {
      const totals: Record<string, number> = {};
      procedureKeys.forEach(k => totals[k] = 0);
      perDoctor.push({ doctor: doc, treatedPatients: 0, sessionCount: 0, procedureTotals: totals });
    }
  }

  const dailyBreakdown = Array.from(dailyMap.entries())
    .map(([date, stats]) => ({ date, ...stats }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return { perDoctor, departmentTotals, dailyBreakdown };
}

// ── Exam Schedule Slots ────────────────────────────────────────────────────
