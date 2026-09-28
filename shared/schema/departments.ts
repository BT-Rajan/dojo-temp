import { pgTable, text, serial, integer, boolean, timestamp, varchar } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { users } from "./auth";
import { centers } from "./centers";

export const departments = pgTable("departments", {
  id: serial("id").primaryKey(),
  centerId: integer("center_id").references(() => centers.id),
  name: text("name").notNull(),
  description: text("description"),
  headUserId: varchar("head_user_id").references(() => users.id),
  callCenterCode: text("call_center_code"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const departmentMembers = pgTable("department_members", {
  id: serial("id").primaryKey(),
  departmentId: integer("department_id").references(() => departments.id).notNull(),
  userId: varchar("user_id").references(() => users.id).notNull(),
  role: text("role").notNull().default("member"), // head, member, viewer, reception, secretary
  canEdit: boolean("can_edit").default(false), // Department heads can edit their dept
  canViewOthers: boolean("can_view_others").default(false), // Can view other dept schedules
  canAssignEmergencies: boolean("can_assign_emergencies").default(false), // Can assign emergency cases
  canManageLeaves: boolean("can_manage_leaves").default(false), // Can manage leave requests
  canViewReports: boolean("can_view_reports").default(false), // Can view reports and statistics
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertDepartmentSchema = createInsertSchema(departments).omit({
  id: true,
  createdAt: true,
});

export const insertDepartmentMemberSchema = createInsertSchema(departmentMembers).omit({
  id: true,
  createdAt: true,
});

export type Department = typeof departments.$inferSelect;
export type InsertDepartment = z.infer<typeof insertDepartmentSchema>;

export type DepartmentMember = typeof departmentMembers.$inferSelect;
export type InsertDepartmentMember = z.infer<typeof insertDepartmentMemberSchema>;
