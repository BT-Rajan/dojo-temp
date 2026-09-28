import { pgTable, text, serial, integer, boolean, timestamp, varchar } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { departments } from "./departments";

export const doctors = pgTable("doctors", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id),
  name: text("name").notNull(),
  title: text("title").notNull(),
  civilId: text("civil_id").notNull(),
  fileNumber: text("file_number").notNull(),
  phone: text("phone").notNull(),
  email: text("email"),
  // Doctor authentication fields
  username: varchar("username").unique(), // For doctor login
  passwordHash: varchar("password_hash"), // For doctor login
  isActive: boolean("is_active").default(true), // Can be deactivated
  lastLogin: timestamp("last_login"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertDoctorSchema = createInsertSchema(doctors).omit({
  id: true,
  createdAt: true,
});

export type Doctor = typeof doctors.$inferSelect;
export type InsertDoctor = z.infer<typeof insertDoctorSchema>;

// Doctor authentication schemas
export const createDoctorAccountSchema = z.object({
  doctorId: z.number(),
  username: z.string().min(3).max(50),
  password: z.string().min(6),
});

export const doctorLoginSchema = z.object({
  username: z.string(),
  password: z.string(),
});
