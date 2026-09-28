import { pgTable, serial, integer, text, date, timestamp } from "drizzle-orm/pg-core";
import { departments } from "./departments";

// Examination schedule — call-center managed weekly calendar
export const examScheduleSlots = pgTable("exam_schedule_slots", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id).notNull(),
  appointmentDate: date("appointment_date").notNull(),
  slotTime: text("slot_time").notNull(), // "HH:MM" e.g. "08:00"
  status: text("status").notNull().default("booked"), // "booked" | "blocked"
  patientName: text("patient_name"),
  patientPhone: text("patient_phone"),
  patientFileId: text("patient_file_id"),
  doctorName: text("doctor_name"),
  notes: text("notes"),
  blockReason: text("block_reason"),
  createdAt: timestamp("created_at").defaultNow(),
});

export type ExamScheduleSlot = typeof examScheduleSlots.$inferSelect;
export type InsertExamScheduleSlot = typeof examScheduleSlots.$inferInsert;
