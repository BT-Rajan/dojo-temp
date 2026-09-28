import { db } from "../db";
import { asc, eq } from "drizzle-orm";
import { systemSettings, type SystemSetting } from "@shared/schema";

// System settings operations
export async function getSystemSetting(key: string): Promise<SystemSetting | undefined> {
  const [setting] = await db.select().from(systemSettings).where(eq(systemSettings.key, key));
  return setting;
}

export async function setSystemSetting(key: string, value: string, description?: string, updatedBy?: string): Promise<SystemSetting> {
  const [setting] = await db
    .insert(systemSettings)
    .values({ key, value, description, updatedBy })
    .onConflictDoUpdate({
      target: systemSettings.key,
      set: {
        value,
        description,
        updatedBy,
        updatedAt: new Date(),
      },
    })
    .returning();
  return setting;
}

export async function getAllSystemSettings(): Promise<SystemSetting[]> {
  return await db.select().from(systemSettings).orderBy(asc(systemSettings.key));
}

