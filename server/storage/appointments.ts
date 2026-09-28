import { db } from "../db";
import { and, asc, desc, eq, gte, lte } from "drizzle-orm";
import {
  doctors, clinics, clinicAssignments, patients, appointmentSlots, appointments, doctorAvailability, leaves, permissions,
  type Doctor, type Clinic, type ClinicAssignment, type Patient, type AppointmentSlot, type InsertAppointmentSlot,
  type Appointment, type InsertAppointment, type DoctorAvailability, type InsertDoctorAvailability,
} from "@shared/schema";
import { getDoctorsByDepartment } from "./doctors";

// Appointment slot operations
export async function getAppointmentSlots(): Promise<AppointmentSlot[]> {
  return await db.select().from(appointmentSlots).where(eq(appointmentSlots.isAvailable, true)).orderBy(asc(appointmentSlots.date), asc(appointmentSlots.startTime));
}

export async function getAppointmentSlotsByDoctor(doctorId: number): Promise<AppointmentSlot[]> {
  return await db.select().from(appointmentSlots).where(and(eq(appointmentSlots.doctorId, doctorId), eq(appointmentSlots.isAvailable, true))).orderBy(asc(appointmentSlots.date), asc(appointmentSlots.startTime));
}

export async function getAppointmentSlotsByDate(date: string): Promise<(AppointmentSlot & { doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointmentSlots)
    .leftJoin(doctors, eq(appointmentSlots.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointmentSlots.clinicId, clinics.id))
    .where(and(eq(appointmentSlots.date, date), eq(appointmentSlots.isAvailable, true)))
    .orderBy(asc(appointmentSlots.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointment_slots,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentSlotsByDoctorAndDate(doctorId: number, date: string): Promise<AppointmentSlot[]> {
  return await db.select().from(appointmentSlots).where(and(eq(appointmentSlots.doctorId, doctorId), eq(appointmentSlots.date, date), eq(appointmentSlots.isAvailable, true))).orderBy(asc(appointmentSlots.startTime));
}

export async function createAppointmentSlot(slot: InsertAppointmentSlot): Promise<AppointmentSlot> {
  const [newSlot] = await db.insert(appointmentSlots).values(slot).returning();
  return newSlot;
}

export async function updateAppointmentSlot(id: number, slot: Partial<InsertAppointmentSlot>): Promise<AppointmentSlot> {
  const [updatedSlot] = await db
    .update(appointmentSlots)
    .set(slot)
    .where(eq(appointmentSlots.id, id))
    .returning();
  return updatedSlot;
}

export async function deleteAppointmentSlot(id: number): Promise<void> {
  await db.update(appointmentSlots).set({ isAvailable: false }).where(eq(appointmentSlots.id, id));
}

// Appointment operations
export async function getAppointments(): Promise<(Appointment & { patient: Patient; doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .orderBy(asc(appointments.appointmentDate), asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentsByDoctor(doctorId: number): Promise<(Appointment & { patient: Patient; clinic?: Clinic })[]> {
  console.log('Fetching appointments for doctor:', doctorId);
  const rows = await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(eq(appointments.doctorId, doctorId))
    .orderBy(asc(appointments.appointmentDate), asc(appointments.startTime));
  
  console.log('Raw appointment rows:', rows.length);
  
  const result = rows.map(row => ({
    ...row.appointments,
    patient: row.patients!,
    clinic: row.clinics || undefined
  }));
  
  console.log('Processed appointments:', result.length, result);
  return result;
}

export async function getAppointmentsByDate(date: string): Promise<(Appointment & { patient: Patient; doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(eq(appointments.appointmentDate, date))
    .orderBy(asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentsByDoctorAndDate(doctorId: number, date: string): Promise<(Appointment & { patient: Patient; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(and(eq(appointments.doctorId, doctorId), eq(appointments.appointmentDate, date)))
    .orderBy(asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentsByDateRange(startDate: string, endDate: string): Promise<(Appointment & { patient: Patient; doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(and(
      gte(appointments.appointmentDate, startDate),
      lte(appointments.appointmentDate, endDate)
    ))
    .orderBy(asc(appointments.appointmentDate), asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentsByDoctorAndDateRange(doctorId: number, startDate: string, endDate: string): Promise<(Appointment & { patient: Patient; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(and(
      eq(appointments.doctorId, doctorId),
      gte(appointments.appointmentDate, startDate),
      lte(appointments.appointmentDate, endDate)
    ))
    .orderBy(asc(appointments.appointmentDate), asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      clinic: row.clinics || undefined
    })));
}

export async function createAppointment(appointment: InsertAppointment): Promise<Appointment> {
  const [newAppointment] = await db.insert(appointments).values(appointment).returning();
  return newAppointment;
}

export async function getAppointmentById(id: number): Promise<Appointment | undefined> {
  const [appointment] = await db.select().from(appointments).where(eq(appointments.id, id));
  return appointment;
}

export async function updateAppointment(id: number, appointment: Partial<InsertAppointment>): Promise<Appointment> {
  const [updatedAppointment] = await db
    .update(appointments)
    .set({ ...appointment, updatedAt: new Date() })
    .where(eq(appointments.id, id))
    .returning();
  return updatedAppointment;
}

export async function updateAppointmentStatus(id: number, status: string): Promise<Appointment> {
  const [updatedAppointment] = await db
    .update(appointments)
    .set({ status, updatedAt: new Date() })
    .where(eq(appointments.id, id))
    .returning();
  return updatedAppointment;
}

export async function deleteAppointment(id: number): Promise<void> {
  // Delete the appointment - no need to delete time slots as they're not a separate table
  await db.delete(appointments).where(eq(appointments.id, id));
}

// Department monitoring methods
export async function getAppointmentsByDepartment(departmentId: number): Promise<(Appointment & { patient: Patient; doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(eq(doctors.departmentId, departmentId))
    .orderBy(asc(appointments.appointmentDate), asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentsByDepartmentAndDate(departmentId: number, date: string): Promise<(Appointment & { patient: Patient; doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      eq(appointments.appointmentDate, date)
    ))
    .orderBy(asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getAppointmentsByDepartmentAndDateRange(departmentId: number, startDate: string, endDate: string): Promise<(Appointment & { patient: Patient; doctor: Doctor; clinic?: Clinic })[]> {
  return await db
    .select()
    .from(appointments)
    .leftJoin(patients, eq(appointments.patientId, patients.id))
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .leftJoin(clinics, eq(appointments.clinicId, clinics.id))
    .where(and(
      eq(doctors.departmentId, departmentId),
      gte(appointments.appointmentDate, startDate),
      lte(appointments.appointmentDate, endDate)
    ))
    .orderBy(asc(appointments.appointmentDate), asc(appointments.startTime))
    .then(rows => rows.map(row => ({
      ...row.appointments,
      patient: row.patients!,
      doctor: row.doctors!,
      clinic: row.clinics || undefined
    })));
}

export async function getDepartmentAppointmentStats(departmentId: number, startDate?: string, endDate?: string): Promise<{
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
  scheduledAppointments: number;
  doctorStats: Array<{
    doctor: Doctor;
    appointmentCount: number;
    completionRate: number;
  }>;
}> {
  let query = db
    .select()
    .from(appointments)
    .leftJoin(doctors, eq(appointments.doctorId, doctors.id))
    .where(eq(doctors.departmentId, departmentId));

  if (startDate && endDate) {
    query = query.where(and(
      eq(doctors.departmentId, departmentId),
      gte(appointments.appointmentDate, startDate),
      lte(appointments.appointmentDate, endDate)
    ));
  }

  const appointmentData = await query;
  
  const totalAppointments = appointmentData.length;
  const completedAppointments = appointmentData.filter(row => row.appointments.status === 'completed').length;
  const cancelledAppointments = appointmentData.filter(row => row.appointments.status === 'cancelled').length;
  const scheduledAppointments = appointmentData.filter(row => row.appointments.status === 'scheduled').length;

  // Calculate doctor stats
  const doctorMap = new Map<number, { doctor: Doctor; total: number; completed: number }>();
  
  appointmentData.forEach(row => {
    const doctorId = row.appointments.doctorId;
    const doctor = row.doctors!;
    
    if (!doctorMap.has(doctorId)) {
      doctorMap.set(doctorId, { doctor, total: 0, completed: 0 });
    }
    
    const stats = doctorMap.get(doctorId)!;
    stats.total++;
    if (row.appointments.status === 'completed') {
      stats.completed++;
    }
  });

  const doctorStats = Array.from(doctorMap.values()).map(stats => ({
    doctor: stats.doctor,
    appointmentCount: stats.total,
    completionRate: stats.total > 0 ? (stats.completed / stats.total) * 100 : 0
  }));

  return {
    totalAppointments,
    completedAppointments,
    cancelledAppointments,
    scheduledAppointments,
    doctorStats
  };
}

export async function getDoctorPerformanceMetrics(departmentId: number, startDate?: string, endDate?: string): Promise<Array<{
  doctor: Doctor;
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
  completionRate: number;
  avgAppointmentsPerDay: number;
  leavesDays: number;
  permissionsCount: number;
}>> {
  // Get all doctors in department
  const departmentDoctors = await getDoctorsByDepartment(departmentId);
  
  const metrics = await Promise.all(departmentDoctors.map(async (doctor) => {
    // Get appointments for this doctor
    let appointmentQuery = db
      .select()
      .from(appointments)
      .where(eq(appointments.doctorId, doctor.id));

    if (startDate && endDate) {
      appointmentQuery = appointmentQuery.where(and(
        eq(appointments.doctorId, doctor.id),
        gte(appointments.appointmentDate, startDate),
        lte(appointments.appointmentDate, endDate)
      ));
    }

    const doctorAppointments = await appointmentQuery;
    
    const totalAppointments = doctorAppointments.length;
    const completedAppointments = doctorAppointments.filter(apt => apt.status === 'completed').length;
    const cancelledAppointments = doctorAppointments.filter(apt => apt.status === 'cancelled').length;
    const completionRate = totalAppointments > 0 ? (completedAppointments / totalAppointments) * 100 : 0;

    // Calculate average appointments per day
    const days = startDate && endDate ? 
      Math.max(1, Math.ceil((new Date(endDate).getTime() - new Date(startDate).getTime()) / (1000 * 60 * 60 * 24))) :
      30; // Default to 30 days if no date range
    const avgAppointmentsPerDay = totalAppointments / days;

    // Get leaves count (days off)
    let leavesQuery = db
      .select()
      .from(leaves)
      .where(eq(leaves.doctorId, doctor.id));

    if (startDate && endDate) {
      leavesQuery = leavesQuery.where(and(
        eq(leaves.doctorId, doctor.id),
        gte(leaves.startDate, startDate),
        lte(leaves.endDate, endDate)
      ));
    }

    const doctorLeaves = await leavesQuery;
    const leavesDays = doctorLeaves.reduce((total, leave) => {
      const start = new Date(leave.startDate);
      const end = new Date(leave.endDate);
      const diffTime = Math.abs(end.getTime() - start.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
      return total + diffDays;
    }, 0);

    // Get permissions count
    let permissionsQuery = db
      .select()
      .from(permissions)
      .where(eq(permissions.doctorId, doctor.id));

    if (startDate && endDate) {
      permissionsQuery = permissionsQuery.where(and(
        eq(permissions.doctorId, doctor.id),
        gte(permissions.date, startDate),
        lte(permissions.date, endDate)
      ));
    }

    const doctorPermissions = await permissionsQuery;
    const permissionsCount = doctorPermissions.length;

    return {
      doctor,
      totalAppointments,
      completedAppointments,
      cancelledAppointments,
      completionRate,
      avgAppointmentsPerDay,
      leavesDays,
      permissionsCount
    };
  }));

  return metrics;
}

// Doctor availability operations
export async function getDoctorAvailability(doctorId: number): Promise<DoctorAvailability[]> {
  return await db.select().from(doctorAvailability).where(and(eq(doctorAvailability.doctorId, doctorId), eq(doctorAvailability.isActive, true))).orderBy(asc(doctorAvailability.weekday), asc(doctorAvailability.startTime));
}

export async function createDoctorAvailability(availability: InsertDoctorAvailability): Promise<DoctorAvailability> {
  const [newAvailability] = await db.insert(doctorAvailability).values(availability).returning();
  return newAvailability;
}

export async function updateDoctorAvailability(id: number, availability: Partial<InsertDoctorAvailability>): Promise<DoctorAvailability> {
  const [updatedAvailability] = await db
    .update(doctorAvailability)
    .set(availability)
    .where(eq(doctorAvailability.id, id))
    .returning();
  return updatedAvailability;
}

export async function deleteDoctorAvailability(id: number): Promise<void> {
  await db.update(doctorAvailability).set({ isActive: false }).where(eq(doctorAvailability.id, id));
}

// Alias methods for doctor dashboard API compatibility - using existing method

export async function getClinicAssignmentsByDoctor(doctorId: number): Promise<(ClinicAssignment & { clinic: Clinic })[]> {
  const results = await db.select()
  .from(clinicAssignments)
  .leftJoin(clinics, eq(clinicAssignments.clinicId, clinics.id))
  .where(eq(clinicAssignments.doctorId, doctorId))
  .orderBy(asc(clinicAssignments.weekday));

  return results.map(row => ({
    id: row.clinic_assignments.id,
    doctorId: row.clinic_assignments.doctorId,
    clinicId: row.clinic_assignments.clinicId,
    weekday: row.clinic_assignments.weekday,
    createdAt: row.clinic_assignments.createdAt,
    isActive: row.clinic_assignments.isActive,
    clinic: row.clinics ? {
      id: row.clinics.id,
      name: row.clinics.name,
      startTime: row.clinics.startTime,
      endTime: row.clinics.endTime,
      departmentId: row.clinics.departmentId,
      description: row.clinics.description,
      createdAt: row.clinics.createdAt
    } : null
  })) as (ClinicAssignment & { clinic: Clinic })[];
}

// Use existing getPermissionsByDoctor method above

