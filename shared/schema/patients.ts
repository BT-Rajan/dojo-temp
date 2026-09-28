import { pgTable, text, serial, integer, boolean, timestamp, date } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { departments } from "./departments";

// Patient management table
export const patients = pgTable("patients", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  civilId: text("civil_id").unique(),
  phone: text("phone").notNull(),
  email: text("email"),
  dateOfBirth: date("date_of_birth"),
  gender: text("gender"), // male, female
  address: text("address"),
  emergencyContact: text("emergency_contact"),
  emergencyPhone: text("emergency_phone"),
  medicalHistory: text("medical_history"),
  allergies: text("allergies"),
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const insertPatientSchema = createInsertSchema(patients).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});

export type Patient = typeof patients.$inferSelect;
export type InsertPatient = z.infer<typeof insertPatientSchema>;
