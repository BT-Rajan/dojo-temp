import { pgTable, serial, integer, text, boolean, date, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { departments } from "./departments";
import { doctors } from "./doctors";

// Overtime Sessions - each clinic row opened for a specific date
export const overtimeSessions = pgTable("overtime_sessions", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id).notNull(),
  clinicName: text("clinic_name").notNull(),
  doctorId: integer("doctor_id").references(() => doctors.id),
  sessionDate: date("session_date").notNull(),
  isOpen: boolean("is_open").default(true),
  notes: text("notes"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Overtime Slot Entries - patient data per time slot per session
export const overtimeSlotEntries = pgTable("overtime_slot_entries", {
  id: serial("id").primaryKey(),
  sessionId: integer("session_id").references(() => overtimeSessions.id).notNull(),
  timeSlot: text("time_slot").notNull(), // "14:00-15:00", "15:00-16:00", "16:00-17:00", "17:00-18:00"
  patientName: text("patient_name"),
  civilId: text("civil_id"),
  phone: text("phone"),
  procedure: text("procedure"),
  notes: text("notes"),
  status: text("status"), // "completed", "cancelled", "no_show", or null
  createdAt: timestamp("created_at").defaultNow(),
});

// Overtime Procedure Logs - one log per overtime session (separate from regular procedure_logs)
export const overtimeProcedureLogs = pgTable("overtime_procedure_logs", {
  id: serial("id").primaryKey(),
  sessionId: integer("session_id").references(() => overtimeSessions.id).notNull().unique(),
  doctorId: integer("doctor_id").notNull().references(() => doctors.id),
  departmentId: integer("department_id").notNull().references(() => departments.id),
  sessionDate: date("session_date").notNull(),
  treatedPatients: integer("treated_patients").default(0),
  alginatePreparation: integer("alginate_preparation").default(0),
  crownPreparation: integer("crown_preparation").default(0),
  bridgePreparation: integer("bridge_preparation").default(0),
  finalImpression: integer("final_impression").default(0),
  tempCementation: integer("temp_cementation").default(0),
  cementAccBb: integer("cement_acc_bb").default(0),
  cementPorcelainCb: integer("cement_porcelain_cb").default(0),
  metalCrownCb: integer("metal_crown_cb").default(0),
  porcelainCb: integer("porcelain_cb").default(0),
  postPreparation: integer("post_preparation").default(0),
  postCanal: integer("post_canal").default(0),
  compositeFilling: integer("composite_filling").default(0),
  amalgamFilling: integer("amalgam_filling").default(0),
  removableProstho: integer("removable_prostho").default(0),
  removableProsthoRepair: integer("removable_prostho_repair").default(0),
  cbRemovalPostCore: integer("cb_removal_post_core").default(0),
  orthoAppliances: integer("ortho_appliances").default(0),
  buckleAppointment: integer("buckle_appointment").default(0),
  implantUnits: integer("implant_units").default(0),
  tryIn: integer("try_in").default(0),
  miscellaneous: integer("miscellaneous").default(0),
  examination: integer("examination").default(0),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Overtime Slot Procedure Logs - one log per patient (slot entry), replacing per-session logs
export const overtimeSlotProcedureLogs = pgTable("overtime_slot_procedure_logs", {
  id: serial("id").primaryKey(),
  slotEntryId: integer("slot_entry_id").references(() => overtimeSlotEntries.id).notNull().unique(),
  alginatePreparation: integer("alginate_preparation").default(0),
  crownPreparation: integer("crown_preparation").default(0),
  bridgePreparation: integer("bridge_preparation").default(0),
  finalImpression: integer("final_impression").default(0),
  tempCementation: integer("temp_cementation").default(0),
  cementAccBb: integer("cement_acc_bb").default(0),
  cementPorcelainCb: integer("cement_porcelain_cb").default(0),
  metalCrownCb: integer("metal_crown_cb").default(0),
  porcelainCb: integer("porcelain_cb").default(0),
  postPreparation: integer("post_preparation").default(0),
  postCanal: integer("post_canal").default(0),
  compositeFilling: integer("composite_filling").default(0),
  amalgamFilling: integer("amalgam_filling").default(0),
  removableProstho: integer("removable_prostho").default(0),
  removableProsthoRepair: integer("removable_prostho_repair").default(0),
  cbRemovalPostCore: integer("cb_removal_post_core").default(0),
  orthoAppliances: integer("ortho_appliances").default(0),
  buckleAppointment: integer("buckle_appointment").default(0),
  implantUnits: integer("implant_units").default(0),
  tryIn: integer("try_in").default(0),
  miscellaneous: integer("miscellaneous").default(0),
  examination: integer("examination").default(0),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const insertOvertimeSessionSchema = createInsertSchema(overtimeSessions).omit({
  id: true,
  createdAt: true,
});

export const insertOvertimeSlotEntrySchema = createInsertSchema(overtimeSlotEntries).omit({
  id: true,
  createdAt: true,
});

export const insertOvertimeProcedureLogSchema = createInsertSchema(overtimeProcedureLogs).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});

export const insertOvertimeSlotProcedureLogSchema = createInsertSchema(overtimeSlotProcedureLogs).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});

export type OvertimeSession = typeof overtimeSessions.$inferSelect;
export type InsertOvertimeSession = z.infer<typeof insertOvertimeSessionSchema>;

export type OvertimeSlotEntry = typeof overtimeSlotEntries.$inferSelect;
export type InsertOvertimeSlotEntry = z.infer<typeof insertOvertimeSlotEntrySchema>;

export type OvertimeProcedureLog = typeof overtimeProcedureLogs.$inferSelect;
export type InsertOvertimeProcedureLog = z.infer<typeof insertOvertimeProcedureLogSchema>;

export type OvertimeSlotProcedureLog = typeof overtimeSlotProcedureLogs.$inferSelect;
export type InsertOvertimeSlotProcedureLog = z.infer<typeof insertOvertimeSlotProcedureLogSchema>;
