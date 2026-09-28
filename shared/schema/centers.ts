import { pgTable, text, serial, integer, boolean, timestamp, varchar } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";
import { users } from "./auth";

export const centers = pgTable("centers", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  description: text("description"),
  isActive: boolean("is_active").default(true),
  createdBy: varchar("created_by").references(() => users.id),
  createdAt: timestamp("created_at").defaultNow(),
});

export const centerMembers = pgTable("center_members", {
  id: serial("id").primaryKey(),
  centerId: integer("center_id").references(() => centers.id).notNull(),
  userId: varchar("user_id").references(() => users.id).notNull(),
  role: text("role").notNull().default("member"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const insertCenterSchema = createInsertSchema(centers).omit({
  id: true,
  createdAt: true,
});

export const insertCenterMemberSchema = createInsertSchema(centerMembers).omit({
  id: true,
  createdAt: true,
});

export const updateCenterNameSchema = z.object({
  centerName: z.string().min(1).max(100),
});

export type Center = typeof centers.$inferSelect;
export type InsertCenter = z.infer<typeof insertCenterSchema>;

export type CenterMember = typeof centerMembers.$inferSelect;
export type InsertCenterMember = z.infer<typeof insertCenterMemberSchema>;
