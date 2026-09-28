import { pgTable, serial, integer, date, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { appointments } from "./appointments";
import { doctors } from "./doctors";
import { departments } from "./departments";

// Procedure logging table for dental procedures tracking
export const procedureLogs = pgTable("procedure_logs", {
  id: serial("id").primaryKey(),
  appointmentId: integer("appointment_id").notNull().references(() => appointments.id),
  doctorId: integer("doctor_id").notNull().references(() => doctors.id),
  departmentId: integer("department_id").notNull().references(() => departments.id),
  procedureDate: date("procedure_date").notNull(),
  // Dental procedures from the CSV template
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
});

export const insertProcedureLogSchema = createInsertSchema(procedureLogs).omit({
  id: true,
  createdAt: true,
});

export type ProcedureLog = typeof procedureLogs.$inferSelect;
export type InsertProcedureLog = z.infer<typeof insertProcedureLogSchema>;
