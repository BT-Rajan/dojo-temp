import { Pool as NeonPool, neonConfig } from '@neondatabase/serverless';
import { drizzle as neonDrizzle } from 'drizzle-orm/neon-serverless';
import { Pool as PgPool } from 'pg';
import { drizzle as pgDrizzle } from 'drizzle-orm/node-postgres';
import ws from "ws";
import * as schema from "@shared/schema";

if (!process.env.DATABASE_URL) {
  throw new Error(
    "DATABASE_URL must be set. Did you forget to provision a database?",
  );
}

// Neon's serverless driver speaks a WebSocket proxy protocol that only
// Neon's own infrastructure understands — it can't talk to a plain local
// Postgres (e.g. the one in docker-compose for local dev). Fall back to the
// standard node-postgres driver for any non-Neon connection string; a real
// Neon DATABASE_URL (production/Replit) keeps using the serverless driver.
const isNeon = /neon\.tech|neon\.build/.test(process.env.DATABASE_URL);

export let pool: NeonPool | PgPool;
export let db: ReturnType<typeof neonDrizzle> | ReturnType<typeof pgDrizzle>;

if (isNeon) {
  neonConfig.webSocketConstructor = ws;
  pool = new NeonPool({ connectionString: process.env.DATABASE_URL });
  db = neonDrizzle({ client: pool, schema });
} else {
  pool = new PgPool({ connectionString: process.env.DATABASE_URL });
  db = pgDrizzle({ client: pool, schema });
}
