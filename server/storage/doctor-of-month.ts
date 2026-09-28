import { db } from "../db";
import { and, desc, eq, gte, lte } from "drizzle-orm";
import {
  doctors, doctorOfTheMonthAwards, appointments,
  type Doctor, type DoctorOfTheMonthAward, type InsertDoctorOfTheMonthAward,
} from "@shared/schema";
import { getDoctorsByDepartment } from "./doctors";

export async function getDoctorOfTheMonthAwards(departmentId: number): Promise<(DoctorOfTheMonthAward & { doctor: Doctor })[]> {
  return await db.select({
    id: doctorOfTheMonthAwards.id,
    doctorId: doctorOfTheMonthAwards.doctorId,
    departmentId: doctorOfTheMonthAwards.departmentId,
    year: doctorOfTheMonthAwards.year,
    month: doctorOfTheMonthAwards.month,
    totalAppointments: doctorOfTheMonthAwards.totalAppointments,
    completedAppointments: doctorOfTheMonthAwards.completedAppointments,
    completionRate: doctorOfTheMonthAwards.completionRate,
    patientSatisfactionScore: doctorOfTheMonthAwards.patientSatisfactionScore,
    punctualityScore: doctorOfTheMonthAwards.punctualityScore,
    overallScore: doctorOfTheMonthAwards.overallScore,
    certificateGenerated: doctorOfTheMonthAwards.certificateGenerated,
    certificateUrl: doctorOfTheMonthAwards.certificateUrl,
    awardedAt: doctorOfTheMonthAwards.awardedAt,
    createdAt: doctorOfTheMonthAwards.createdAt,
    doctor: doctors,
  })
    .from(doctorOfTheMonthAwards)
    .leftJoin(doctors, eq(doctorOfTheMonthAwards.doctorId, doctors.id))
    .where(eq(doctorOfTheMonthAwards.departmentId, departmentId))
    .orderBy(desc(doctorOfTheMonthAwards.year), desc(doctorOfTheMonthAwards.month));
}

export async function getDoctorOfTheMonthForPeriod(departmentId: number, year: number, month: number): Promise<(DoctorOfTheMonthAward & { doctor: Doctor }) | null> {
  const result = await db.select({
    id: doctorOfTheMonthAwards.id,
    doctorId: doctorOfTheMonthAwards.doctorId,
    departmentId: doctorOfTheMonthAwards.departmentId,
    year: doctorOfTheMonthAwards.year,
    month: doctorOfTheMonthAwards.month,
    totalAppointments: doctorOfTheMonthAwards.totalAppointments,
    completedAppointments: doctorOfTheMonthAwards.completedAppointments,
    completionRate: doctorOfTheMonthAwards.completionRate,
    patientSatisfactionScore: doctorOfTheMonthAwards.patientSatisfactionScore,
    punctualityScore: doctorOfTheMonthAwards.punctualityScore,
    overallScore: doctorOfTheMonthAwards.overallScore,
    certificateGenerated: doctorOfTheMonthAwards.certificateGenerated,
    certificateUrl: doctorOfTheMonthAwards.certificateUrl,
    awardedAt: doctorOfTheMonthAwards.awardedAt,
    createdAt: doctorOfTheMonthAwards.createdAt,
    doctor: doctors,
  })
    .from(doctorOfTheMonthAwards)
    .leftJoin(doctors, eq(doctorOfTheMonthAwards.doctorId, doctors.id))
    .where(
      and(
        eq(doctorOfTheMonthAwards.departmentId, departmentId),
        eq(doctorOfTheMonthAwards.year, year),
        eq(doctorOfTheMonthAwards.month, month)
      )
    )
    .limit(1);

  return result[0] || null;
}

export async function createDoctorOfTheMonthAward(award: InsertDoctorOfTheMonthAward): Promise<DoctorOfTheMonthAward> {
  const [newAward] = await db
    .insert(doctorOfTheMonthAwards)
    .values(award)
    .returning();
  return newAward;
}

export async function calculateMonthlyDoctorRankings(departmentId: number, year: number, month: number): Promise<{
  doctorId: number;
  doctor: Doctor;
  totalAppointments: number;
  completedAppointments: number;
  completionRate: number;
  overallScore: number;
}[]> {
  // Get all doctors in the department
  const departmentDoctors = await getDoctorsByDepartment(departmentId);
  
  const rankings = [];
  
  for (const doctor of departmentDoctors) {
    // Get doctor's monthly statistics
    const startDate = new Date(year, month - 1, 1);
    const endDate = new Date(year, month, 0, 23, 59, 59);
    
    const monthlyAppointments = await db.select()
      .from(appointments)
      .where(
        and(
          eq(appointments.doctorId, doctor.id),
          gte(appointments.appointmentDate, startDate.toISOString().split('T')[0]),
          lte(appointments.appointmentDate, endDate.toISOString().split('T')[0])
        )
      );
    
    const totalAppointments = monthlyAppointments.length;
    const completedAppointments = monthlyAppointments.filter(
      appointment => appointment.status === 'completed'
    ).length;
    
    const completionRate = totalAppointments > 0 ? (completedAppointments / totalAppointments) * 100 : 0;
    
    // Calculate overall score (weighted average)
    const overallScore = (
      completionRate * 0.7 + // 70% weight for completion rate
      (totalAppointments > 0 ? 30 : 0) * 0.3 // 30% weight for activity level
    );
    
    rankings.push({
      doctorId: doctor.id,
      doctor,
      totalAppointments,
      completedAppointments,
      completionRate,
      overallScore: Math.round(overallScore * 100) / 100, // Round to 2 decimal places
    });
  }
  
  // Sort by overall score descending
  return rankings.sort((a, b) => b.overallScore - a.overallScore);
}

