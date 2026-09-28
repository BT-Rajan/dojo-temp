import { pgTable, text, serial, integer, boolean, timestamp, date, time } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { departments } from "./departments";
import { doctors } from "./doctors";

export const leaves = pgTable("leaves", {
  id: serial("id").primaryKey(),
  doctorId: integer("doctor_id").references(() => doctors.id).notNull(),
  startDate: date("start_date").notNull(),
  endDate: date("end_date").notNull(),
  type: text("type").notNull().default("annual"), // annual, sick, emergency, etc.
  reason: text("reason"),
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const permissions = pgTable("permissions", {
  id: serial("id").primaryKey(),
  doctorId: integer("doctor_id").references(() => doctors.id).notNull(),
  date: date("date").notNull(),
  type: text("type").notNull(), // start_of_day, end_of_day
  startTime: time("start_time").notNull(),
  endTime: time("end_time").notNull(),
  reason: text("reason"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const emergencyAssignments = pgTable("emergency_assignments", {
  id: serial("id").primaryKey(),
  doctorId: integer("doctor_id").references(() => doctors.id).notNull(),
  assignedDate: date("assigned_date").notNull(),
  assignedTime: time("assigned_time").notNull(),
  emergencyNumber: integer("emergency_number").notNull(),
  patientName: text("patient_name").notNull(),
  emergencyType: text("emergency_type").notNull(),
  notes: text("notes"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const examinationSlots = pgTable("examination_slots", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id),
  weekday: integer("weekday").notNull(), // 0 = Sunday, 1 = Monday, etc.
  startTime: time("start_time").notNull(),
  endTime: time("end_time").notNull(),
  maxDoctors: integer("max_doctors").default(1),
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const examinationAssignments = pgTable("examination_assignments", {
  id: serial("id").primaryKey(),
  slotId: integer("slot_id").references(() => examinationSlots.id).notNull(),
  doctorId: integer("doctor_id").references(() => doctors.id).notNull(),
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertLeaveSchema = createInsertSchema(leaves).omit({
  id: true,
  createdAt: true,
});

export const insertPermissionSchema = createInsertSchema(permissions).omit({
  id: true,
  createdAt: true,
});

export const insertEmergencyAssignmentSchema = createInsertSchema(emergencyAssignments).omit({
  id: true,
  createdAt: true,
});

export const insertExaminationSlotSchema = createInsertSchema(examinationSlots).omit({
  id: true,
  createdAt: true,
});

export const insertExaminationAssignmentSchema = createInsertSchema(examinationAssignments).omit({
  id: true,
  createdAt: true,
});

export type Leave = typeof leaves.$inferSelect;
export type InsertLeave = z.infer<typeof insertLeaveSchema>;

export type Permission = typeof permissions.$inferSelect;
export type InsertPermission = z.infer<typeof insertPermissionSchema>;

export type EmergencyAssignment = typeof emergencyAssignments.$inferSelect;
export type InsertEmergencyAssignment = z.infer<typeof insertEmergencyAssignmentSchema>;

export type ExaminationSlot = typeof examinationSlots.$inferSelect;
export type InsertExaminationSlot = z.infer<typeof insertExaminationSlotSchema>;

export type ExaminationAssignment = typeof examinationAssignments.$inferSelect;
export type InsertExaminationAssignment = z.infer<typeof insertExaminationAssignmentSchema>;
