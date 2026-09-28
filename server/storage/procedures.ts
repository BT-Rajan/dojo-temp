import { db } from "../db";
import { and, desc, eq, gte, lte } from "drizzle-orm";
import { doctors, appointments, procedureLogs, type Doctor, type Appointment, type ProcedureLog, type InsertProcedureLog } from "@shared/schema";
import { getDoctor, getDoctorsByDepartment } from "./doctors";

// Procedure logging operations
export async function getProcedureLogs(): Promise<(ProcedureLog & { doctor: Doctor; appointment: Appointment })[]> {
  return await db
    .select()
    .from(procedureLogs)
    .leftJoin(doctors, eq(procedureLogs.doctorId, doctors.id))
    .leftJoin(appointments, eq(procedureLogs.appointmentId, appointments.id))
    .orderBy(desc(procedureLogs.createdAt));
}

export async function getProcedureLogsByDepartment(departmentId: number): Promise<(ProcedureLog & { doctor: Doctor; appointment: Appointment })[]> {
  return await db
    .select()
    .from(procedureLogs)
    .leftJoin(doctors, eq(procedureLogs.doctorId, doctors.id))
    .leftJoin(appointments, eq(procedureLogs.appointmentId, appointments.id))
    .where(eq(procedureLogs.departmentId, departmentId))
    .orderBy(desc(procedureLogs.createdAt));
}

export async function getProcedureLogsByDoctor(doctorId: number): Promise<ProcedureLog[]> {
  return await db
    .select()
    .from(procedureLogs)
    .where(eq(procedureLogs.doctorId, doctorId))
    .orderBy(desc(procedureLogs.createdAt));
}

export async function getProcedureLogsByDateRange(startDate: string, endDate: string): Promise<(ProcedureLog & { doctor: Doctor; appointment: Appointment })[]> {
  return await db
    .select()
    .from(procedureLogs)
    .leftJoin(doctors, eq(procedureLogs.doctorId, doctors.id))
    .leftJoin(appointments, eq(procedureLogs.appointmentId, appointments.id))
    .where(
      and(
        gte(procedureLogs.procedureDate, startDate),
        lte(procedureLogs.procedureDate, endDate)
      )
    )
    .orderBy(desc(procedureLogs.createdAt));
}

export async function getProcedureLogsByDoctorAndDateRange(doctorId: number, startDate: string, endDate: string): Promise<ProcedureLog[]> {
  return await db
    .select()
    .from(procedureLogs)
    .where(
      and(
        eq(procedureLogs.doctorId, doctorId),
        gte(procedureLogs.procedureDate, startDate),
        lte(procedureLogs.procedureDate, endDate)
      )
    )
    .orderBy(desc(procedureLogs.createdAt));
}

export async function createProcedureLog(procedureLog: InsertProcedureLog): Promise<ProcedureLog> {
  const [newLog] = await db
    .insert(procedureLogs)
    .values(procedureLog)
    .returning();
  return newLog;
}

export async function getProcedureStatsByDoctor(doctorId: number, year?: number, month?: number): Promise<{
  totalAppointments: number;
  completedAppointments: number;
  procedureTotals: Record<string, number>;
}> {
  let dateFilter = eq(procedureLogs.doctorId, doctorId);
  
  if (year && month) {
    const startDate = new Date(year, month - 1, 1);
    const endDate = new Date(year, month, 0);
    dateFilter = and(
      eq(procedureLogs.doctorId, doctorId),
      gte(procedureLogs.procedureDate, startDate.toISOString().split('T')[0]),
      lte(procedureLogs.procedureDate, endDate.toISOString().split('T')[0])
    );
  }
  
  const logs = await db
    .select()
    .from(procedureLogs)
    .where(dateFilter);
  
  const procedureTotals: Record<string, number> = {};
  let totalAppointments = 0;
  
  logs.forEach(log => {
    totalAppointments += log.treatedPatients || 0;
    procedureTotals['alginatePreparation'] = (procedureTotals['alginatePreparation'] || 0) + (log.alginatePreparation || 0);
    procedureTotals['crownPreparation'] = (procedureTotals['crownPreparation'] || 0) + (log.crownPreparation || 0);
    procedureTotals['bridgePreparation'] = (procedureTotals['bridgePreparation'] || 0) + (log.bridgePreparation || 0);
    procedureTotals['finalImpression'] = (procedureTotals['finalImpression'] || 0) + (log.finalImpression || 0);
    procedureTotals['tempCementation'] = (procedureTotals['tempCementation'] || 0) + (log.tempCementation || 0);
    procedureTotals['cementAccBb'] = (procedureTotals['cementAccBb'] || 0) + (log.cementAccBb || 0);
    procedureTotals['cementPorcelainCb'] = (procedureTotals['cementPorcelainCb'] || 0) + (log.cementPorcelainCb || 0);
    procedureTotals['metalCrownCb'] = (procedureTotals['metalCrownCb'] || 0) + (log.metalCrownCb || 0);
    procedureTotals['porcelainCb'] = (procedureTotals['porcelainCb'] || 0) + (log.porcelainCb || 0);
    procedureTotals['postPreparation'] = (procedureTotals['postPreparation'] || 0) + (log.postPreparation || 0);
    procedureTotals['postCanal'] = (procedureTotals['postCanal'] || 0) + (log.postCanal || 0);
    procedureTotals['compositeFilling'] = (procedureTotals['compositeFilling'] || 0) + (log.compositeFilling || 0);
    procedureTotals['amalgamFilling'] = (procedureTotals['amalgamFilling'] || 0) + (log.amalgamFilling || 0);
    procedureTotals['removableProstho'] = (procedureTotals['removableProstho'] || 0) + (log.removableProstho || 0);
    procedureTotals['removableProsthoRepair'] = (procedureTotals['removableProsthoRepair'] || 0) + (log.removableProsthoRepair || 0);
    procedureTotals['cbRemovalPostCore'] = (procedureTotals['cbRemovalPostCore'] || 0) + (log.cbRemovalPostCore || 0);
    procedureTotals['orthoAppliances'] = (procedureTotals['orthoAppliances'] || 0) + (log.orthoAppliances || 0);
    procedureTotals['buckleAppointment'] = (procedureTotals['buckleAppointment'] || 0) + (log.buckleAppointment || 0);
    procedureTotals['implantUnits'] = (procedureTotals['implantUnits'] || 0) + (log.implantUnits || 0);
  });
  
  return {
    totalAppointments,
    completedAppointments: logs.length, // Each log represents a completed appointment
    procedureTotals,
  };
}

export async function getProcedureStatsByDepartment(departmentId: number, year?: number, month?: number): Promise<Array<{
  doctor: Doctor;
  totalAppointments: number;
  completedAppointments: number;
  procedureTotals: Record<string, number>;
}>> {
  const departmentDoctors = await getDoctorsByDepartment(departmentId);
  const results = [];
  
  for (const doctor of departmentDoctors) {
    const stats = await getProcedureStatsByDoctor(doctor.id, year, month);
    results.push({
      doctor,
      ...stats,
    });
  }
  
  return results;
}

export async function getAggregatedProcedureStats(departmentId: number, startDate: string, endDate: string, doctorId?: number): Promise<{
  perDoctor: Array<{
    doctor: Doctor;
    treatedPatients: number;
    completedAppointments: number;
    procedureTotals: Record<string, number>;
  }>;
  departmentTotals: {
    treatedPatients: number;
    completedAppointments: number;
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
    'orthoAppliances', 'buckleAppointment', 'implantUnits'
  ];

  const conditions = [
    eq(procedureLogs.departmentId, departmentId),
    gte(procedureLogs.procedureDate, startDate),
    lte(procedureLogs.procedureDate, endDate)
  ];
  if (doctorId) {
    conditions.push(eq(procedureLogs.doctorId, doctorId));
  }

  const logs = await db
    .select()
    .from(procedureLogs)
    .where(and(...conditions))
    .orderBy(procedureLogs.procedureDate);

  const departmentDoctors = doctorId
    ? [await getDoctor(doctorId)].filter(Boolean) as Doctor[]
    : await getDoctorsByDepartment(departmentId);

  const doctorMap = new Map<number, Doctor>();
  departmentDoctors.forEach(d => doctorMap.set(d.id, d));

  const perDoctorMap = new Map<number, { treatedPatients: number; completedAppointments: number; procedureTotals: Record<string, number> }>();
  const dailyMap = new Map<string, { treatedPatients: number; totalProcedures: number }>();
  const departmentTotals = { treatedPatients: 0, completedAppointments: 0, procedureTotals: {} as Record<string, number> };
  procedureKeys.forEach(k => departmentTotals.procedureTotals[k] = 0);

  for (const log of logs) {
    if (!perDoctorMap.has(log.doctorId)) {
      const totals: Record<string, number> = {};
      procedureKeys.forEach(k => totals[k] = 0);
      perDoctorMap.set(log.doctorId, { treatedPatients: 0, completedAppointments: 0, procedureTotals: totals });
    }
    const docStats = perDoctorMap.get(log.doctorId)!;
    const treated = log.treatedPatients || 0;
    docStats.treatedPatients += treated;
    docStats.completedAppointments += 1;
    departmentTotals.treatedPatients += treated;
    departmentTotals.completedAppointments += 1;

    let dayProcedures = 0;
    for (const key of procedureKeys) {
      const val = (log as any)[key] || 0;
      docStats.procedureTotals[key] += val;
      departmentTotals.procedureTotals[key] += val;
      dayProcedures += val;
    }

    const dateStr = log.procedureDate;
    if (!dailyMap.has(dateStr)) {
      dailyMap.set(dateStr, { treatedPatients: 0, totalProcedures: 0 });
    }
    const day = dailyMap.get(dateStr)!;
    day.treatedPatients += treated;
    day.totalProcedures += dayProcedures;
  }

  const perDoctor = Array.from(perDoctorMap.entries())
    .filter(([id]) => doctorMap.has(id))
    .map(([id, stats]) => ({
      doctor: doctorMap.get(id)!,
      ...stats,
    }));

  for (const doc of departmentDoctors) {
    if (!perDoctorMap.has(doc.id)) {
      const totals: Record<string, number> = {};
      procedureKeys.forEach(k => totals[k] = 0);
      perDoctor.push({ doctor: doc, treatedPatients: 0, completedAppointments: 0, procedureTotals: totals });
    }
  }

  const dailyBreakdown = Array.from(dailyMap.entries())
    .map(([date, stats]) => ({ date, ...stats }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return { perDoctor, departmentTotals, dailyBreakdown };
}

