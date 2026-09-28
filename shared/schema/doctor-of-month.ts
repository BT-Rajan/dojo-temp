import { pgTable, serial, integer, boolean, timestamp, real, varchar, unique } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { doctors } from "./doctors";
import { departments } from "./departments";

// Doctor of the Month Awards table
export const doctorOfTheMonthAwards = pgTable("doctor_of_the_month_awards", {
  id: serial("id").primaryKey(),
  doctorId: integer("doctor_id").notNull().references(() => doctors.id),
  departmentId: integer("department_id").notNull().references(() => departments.id),
  year: integer("year").notNull(),
  month: integer("month").notNull(), // 1-12
  totalAppointments: integer("total_appointments").notNull().default(0),
  completedAppointments: integer("completed_appointments").notNull().default(0),
  completionRate: real("completion_rate").notNull().default(0), // percentage
  patientSatisfactionScore: real("patient_satisfaction_score").default(0), // 1-5 scale
  punctualityScore: real("punctuality_score").default(0), // percentage
  overallScore: real("overall_score").notNull().default(0), // calculated composite score
  certificateGenerated: boolean("certificate_generated").default(false),
  certificateUrl: varchar("certificate_url", { length: 500 }),
  awardedAt: timestamp("awarded_at").defaultNow(),
  createdAt: timestamp("created_at").defaultNow(),
}, (table) => ({
  // Unique constraint to ensure one award per doctor per month per department
  uniqueMonthlyAward: unique().on(table.doctorId, table.departmentId, table.year, table.month),
}));

export const insertDoctorOfTheMonthAwardSchema = createInsertSchema(doctorOfTheMonthAwards).omit({
  id: true,
  createdAt: true,
  awardedAt: true,
});

export type DoctorOfTheMonthAward = typeof doctorOfTheMonthAwards.$inferSelect;
export type InsertDoctorOfTheMonthAward = typeof doctorOfTheMonthAwards.$inferInsert;
