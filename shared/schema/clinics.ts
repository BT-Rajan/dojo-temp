import { pgTable, text, serial, integer, boolean, timestamp, time } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { departments } from "./departments";
import { doctors } from "./doctors";

export const clinics = pgTable("clinics", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id),
  name: text("name").notNull(),
  description: text("description"),
  startTime: time("start_time").notNull(),
  endTime: time("end_time").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
});

export const clinicAssignments = pgTable("clinic_assignments", {
  id: serial("id").primaryKey(),
  doctorId: integer("doctor_id").references(() => doctors.id).notNull(),
  clinicId: integer("clinic_id").references(() => clinics.id).notNull(),
  weekday: integer("weekday").notNull(), // 0 = Sunday, 1 = Monday, etc.
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertClinicSchema = createInsertSchema(clinics).omit({
  id: true,
  createdAt: true,
});

export const insertClinicAssignmentSchema = createInsertSchema(clinicAssignments).omit({
  id: true,
  createdAt: true,
});

export type Clinic = typeof clinics.$inferSelect;
export type InsertClinic = z.infer<typeof insertClinicSchema>;

export type ClinicAssignment = typeof clinicAssignments.$inferSelect;
export type InsertClinicAssignment = z.infer<typeof insertClinicAssignmentSchema>;
