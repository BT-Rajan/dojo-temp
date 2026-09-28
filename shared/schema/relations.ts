import { relations } from "drizzle-orm";
import { users } from "./auth";
import { centers, centerMembers } from "./centers";
import { departments, departmentMembers } from "./departments";
import { doctors } from "./doctors";
import { clinics, clinicAssignments } from "./clinics";
import { leaves, permissions, emergencyAssignments, examinationSlots, examinationAssignments } from "./scheduling";
import { patients } from "./patients";
import { appointmentSlots, appointments, doctorAvailability } from "./appointments";
import { doctorOfTheMonthAwards } from "./doctor-of-month";
import { procedureLogs } from "./procedures";

// All cross-table relations live here in one place, rather than split across
// each domain file, so that no two domain files need to import each other
// just to describe the "many" side of a relationship.
export const usersRelations = relations(users, ({ many }) => ({
  departments: many(departments),
  membershipDepartments: many(departmentMembers),
  centerMemberships: many(centerMembers),
}));

export const centersRelations = relations(centers, ({ many, one }) => ({
  createdByUser: one(users, {
    fields: [centers.createdBy],
    references: [users.id],
  }),
  departments: many(departments),
  members: many(centerMembers),
}));

export const centerMembersRelations = relations(centerMembers, ({ one }) => ({
  center: one(centers, {
    fields: [centerMembers.centerId],
    references: [centers.id],
  }),
  user: one(users, {
    fields: [centerMembers.userId],
    references: [users.id],
  }),
}));

export const departmentsRelations = relations(departments, ({ many, one }) => ({
  center: one(centers, {
    fields: [departments.centerId],
    references: [centers.id],
  }),
  head: one(users, {
    fields: [departments.headUserId],
    references: [users.id],
  }),
  members: many(departmentMembers),
  doctors: many(doctors),
  clinics: many(clinics),
  examinationSlots: many(examinationSlots),
}));

export const departmentMembersRelations = relations(departmentMembers, ({ one }) => ({
  department: one(departments, {
    fields: [departmentMembers.departmentId],
    references: [departments.id],
  }),
  user: one(users, {
    fields: [departmentMembers.userId],
    references: [users.id],
  }),
}));

export const doctorsRelations = relations(doctors, ({ many, one }) => ({
  department: one(departments, {
    fields: [doctors.departmentId],
    references: [departments.id],
  }),
  clinicAssignments: many(clinicAssignments),
  leaves: many(leaves),
  permissions: many(permissions),
  emergencyAssignments: many(emergencyAssignments),
  examinationAssignments: many(examinationAssignments),
  appointmentSlots: many(appointmentSlots),
  appointments: many(appointments),
  availability: many(doctorAvailability),
  monthlyAwards: many(doctorOfTheMonthAwards),
  procedureLogs: many(procedureLogs),
}));

export const clinicsRelations = relations(clinics, ({ many, one }) => ({
  department: one(departments, {
    fields: [clinics.departmentId],
    references: [departments.id],
  }),
  assignments: many(clinicAssignments),
}));

export const clinicAssignmentsRelations = relations(clinicAssignments, ({ one }) => ({
  doctor: one(doctors, {
    fields: [clinicAssignments.doctorId],
    references: [doctors.id],
  }),
  clinic: one(clinics, {
    fields: [clinicAssignments.clinicId],
    references: [clinics.id],
  }),
}));

export const leavesRelations = relations(leaves, ({ one }) => ({
  doctor: one(doctors, {
    fields: [leaves.doctorId],
    references: [doctors.id],
  }),
}));

export const permissionsRelations = relations(permissions, ({ one }) => ({
  doctor: one(doctors, {
    fields: [permissions.doctorId],
    references: [doctors.id],
  }),
}));

export const emergencyAssignmentsRelations = relations(emergencyAssignments, ({ one }) => ({
  doctor: one(doctors, {
    fields: [emergencyAssignments.doctorId],
    references: [doctors.id],
  }),
}));

export const examinationSlotsRelations = relations(examinationSlots, ({ many, one }) => ({
  department: one(departments, {
    fields: [examinationSlots.departmentId],
    references: [departments.id],
  }),
  assignments: many(examinationAssignments),
}));

export const examinationAssignmentsRelations = relations(examinationAssignments, ({ one }) => ({
  slot: one(examinationSlots, {
    fields: [examinationAssignments.slotId],
    references: [examinationSlots.id],
  }),
  doctor: one(doctors, {
    fields: [examinationAssignments.doctorId],
    references: [doctors.id],
  }),
}));

export const patientsRelations = relations(patients, ({ many, one }) => ({
  department: one(departments, {
    fields: [patients.departmentId],
    references: [departments.id],
  }),
  appointments: many(appointments),
}));

export const appointmentSlotsRelations = relations(appointmentSlots, ({ many, one }) => ({
  doctor: one(doctors, {
    fields: [appointmentSlots.doctorId],
    references: [doctors.id],
  }),
  clinic: one(clinics, {
    fields: [appointmentSlots.clinicId],
    references: [clinics.id],
  }),
  appointments: many(appointments),
}));

export const appointmentsRelations = relations(appointments, ({ one, many }) => ({
  slot: one(appointmentSlots, {
    fields: [appointments.slotId],
    references: [appointmentSlots.id],
  }),
  patient: one(patients, {
    fields: [appointments.patientId],
    references: [patients.id],
  }),
  doctor: one(doctors, {
    fields: [appointments.doctorId],
    references: [doctors.id],
  }),
  clinic: one(clinics, {
    fields: [appointments.clinicId],
    references: [clinics.id],
  }),
  procedureLogs: many(procedureLogs),
}));

export const doctorAvailabilityRelations = relations(doctorAvailability, ({ one }) => ({
  doctor: one(doctors, {
    fields: [doctorAvailability.doctorId],
    references: [doctors.id],
  }),
}));

export const doctorOfTheMonthAwardsRelations = relations(doctorOfTheMonthAwards, ({ one }) => ({
  doctor: one(doctors, {
    fields: [doctorOfTheMonthAwards.doctorId],
    references: [doctors.id],
  }),
  department: one(departments, {
    fields: [doctorOfTheMonthAwards.departmentId],
    references: [departments.id],
  }),
}));

export const procedureLogsRelations = relations(procedureLogs, ({ one }) => ({
  appointment: one(appointments, {
    fields: [procedureLogs.appointmentId],
    references: [appointments.id],
  }),
  doctor: one(doctors, {
    fields: [procedureLogs.doctorId],
    references: [doctors.id],
  }),
  department: one(departments, {
    fields: [procedureLogs.departmentId],
    references: [departments.id],
  }),
}));
