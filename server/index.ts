import express, { type Request, Response, NextFunction } from "express";
import { createServer } from "http";
import { WebSocketServer } from "ws";
import { registerRoutes } from "./routes";
import { setupVite, serveStatic, log } from "./vite";
import { storage } from "./storage";

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.use((req, res, next) => {
  const start = Date.now();
  const path = req.path;
  let capturedJsonResponse: Record<string, any> | undefined = undefined;

  const originalResJson = res.json;
  res.json = function (bodyJson, ...args) {
    capturedJsonResponse = bodyJson;
    return originalResJson.apply(res, [bodyJson, ...args]);
  };

  res.on("finish", () => {
    const duration = Date.now() - start;
    if (path.startsWith("/api")) {
      let logLine = `${req.method} ${path} ${res.statusCode} in ${duration}ms`;
      if (capturedJsonResponse) {
        logLine += ` :: ${JSON.stringify(capturedJsonResponse)}`;
      }

      if (logLine.length > 80) {
        logLine = logLine.slice(0, 79) + "…";
      }

      log(logLine);
    }
  });

  next();
});

// WebSocket connections map: userId -> WebSocket
export const wsConnections = new Map<string, any>();

async function runSchemaMigrations() {
  try {
    const { db } = await import("./db");
    const { sql } = await import("drizzle-orm");
    await db.execute(sql`
      ALTER TABLE procedure_logs
        ADD COLUMN IF NOT EXISTS try_in integer DEFAULT 0,
        ADD COLUMN IF NOT EXISTS miscellaneous integer DEFAULT 0,
        ADD COLUMN IF NOT EXISTS examination integer DEFAULT 0
    `);
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS overtime_sessions (
        id serial PRIMARY KEY,
        department_id integer NOT NULL REFERENCES departments(id),
        clinic_name text NOT NULL,
        doctor_id integer REFERENCES doctors(id),
        session_date date NOT NULL,
        is_open boolean DEFAULT true,
        notes text,
        created_at timestamp DEFAULT now()
      )
    `);
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS overtime_slot_entries (
        id serial PRIMARY KEY,
        session_id integer NOT NULL REFERENCES overtime_sessions(id),
        time_slot text NOT NULL,
        patient_name text,
        civil_id text,
        phone text,
        procedure text,
        notes text,
        created_at timestamp DEFAULT now()
      )
    `);
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS overtime_procedure_logs (
        id serial PRIMARY KEY,
        session_id integer NOT NULL UNIQUE REFERENCES overtime_sessions(id),
        doctor_id integer NOT NULL REFERENCES doctors(id),
        department_id integer NOT NULL REFERENCES departments(id),
        session_date date NOT NULL,
        treated_patients integer DEFAULT 0,
        alginate_preparation integer DEFAULT 0,
        crown_preparation integer DEFAULT 0,
        bridge_preparation integer DEFAULT 0,
        final_impression integer DEFAULT 0,
        temp_cementation integer DEFAULT 0,
        cement_acc_bb integer DEFAULT 0,
        cement_porcelain_cb integer DEFAULT 0,
        metal_crown_cb integer DEFAULT 0,
        porcelain_cb integer DEFAULT 0,
        post_preparation integer DEFAULT 0,
        post_canal integer DEFAULT 0,
        composite_filling integer DEFAULT 0,
        amalgam_filling integer DEFAULT 0,
        removable_prostho integer DEFAULT 0,
        removable_prostho_repair integer DEFAULT 0,
        cb_removal_post_core integer DEFAULT 0,
        ortho_appliances integer DEFAULT 0,
        buckle_appointment integer DEFAULT 0,
        implant_units integer DEFAULT 0,
        try_in integer DEFAULT 0,
        miscellaneous integer DEFAULT 0,
        examination integer DEFAULT 0,
        created_at timestamp DEFAULT now(),
        updated_at timestamp DEFAULT now()
      )
    `);
    await db.execute(sql`
      ALTER TABLE overtime_slot_entries
        ADD COLUMN IF NOT EXISTS status text
    `);
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS overtime_slot_procedure_logs (
        id serial PRIMARY KEY,
        slot_entry_id integer NOT NULL UNIQUE REFERENCES overtime_slot_entries(id),
        alginate_preparation integer DEFAULT 0,
        crown_preparation integer DEFAULT 0,
        bridge_preparation integer DEFAULT 0,
        final_impression integer DEFAULT 0,
        temp_cementation integer DEFAULT 0,
        cement_acc_bb integer DEFAULT 0,
        cement_porcelain_cb integer DEFAULT 0,
        metal_crown_cb integer DEFAULT 0,
        porcelain_cb integer DEFAULT 0,
        post_preparation integer DEFAULT 0,
        post_canal integer DEFAULT 0,
        composite_filling integer DEFAULT 0,
        amalgam_filling integer DEFAULT 0,
        removable_prostho integer DEFAULT 0,
        removable_prostho_repair integer DEFAULT 0,
        cb_removal_post_core integer DEFAULT 0,
        ortho_appliances integer DEFAULT 0,
        buckle_appointment integer DEFAULT 0,
        implant_units integer DEFAULT 0,
        try_in integer DEFAULT 0,
        miscellaneous integer DEFAULT 0,
        examination integer DEFAULT 0,
        created_at timestamp DEFAULT now(),
        updated_at timestamp DEFAULT now()
      )
    `);
    await db.execute(sql`
      ALTER TABLE departments
        ADD COLUMN IF NOT EXISTS call_center_code text
    `);
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS exam_schedule_slots (
        id serial PRIMARY KEY,
        department_id integer NOT NULL REFERENCES departments(id),
        appointment_date date NOT NULL,
        slot_time text NOT NULL,
        status text NOT NULL DEFAULT 'booked',
        patient_name text,
        patient_phone text,
        patient_file_id text,
        doctor_name text,
        notes text,
        block_reason text,
        created_at timestamp DEFAULT now()
      )
    `);
    log("Schema migrations applied successfully");
  } catch (error) {
    log(`Error running schema migrations: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function ensureDefaultCentersExist() {
  try {
    const allCenters = await storage.getCenters();
    if (allCenters.length === 0) {
      log("No centers found - creating default centers and memberships...");
      
      const center1 = await storage.createCenter({
        name: "Al-Adan Dental Specialty Center",
        description: "Main dental specialty center",
        createdBy: "45172850",
      });
      
      const center2 = await storage.createCenter({
        name: "Al-Amiri",
        description: "",
        createdBy: "45172850",
      });

      const { db } = await import("./db");
      const { users } = await import("@shared/schema");
      const allUsers = await db.select().from(users);
      for (const user of allUsers) {
        try {
          await storage.addCenterMember({
            centerId: center1.id,
            userId: user.id,
            role: user.isCenterHead ? "admin" : "member",
          });
        } catch (e) {}
      }

      try {
        await storage.addCenterMember({
          centerId: center2.id,
          userId: "45172850",
          role: "admin",
        });
      } catch (e) {}

      log(`Created 2 centers and enrolled users`);
    }

    const { db } = await import("./db");
    const { departments } = await import("@shared/schema");
    const { isNull } = await import("drizzle-orm");
    const depsWithoutCenter = await db.select().from(departments).where(isNull(departments.centerId));
    if (depsWithoutCenter.length > 0) {
      const firstCenter = allCenters.length > 0 ? allCenters[0] : (await storage.getCenters())[0];
      if (firstCenter) {
        const { eq } = await import("drizzle-orm");
        for (const dept of depsWithoutCenter) {
          await db.update(departments).set({ centerId: firstCenter.id }).where(eq(departments.id, dept.id));
        }
        log(`Assigned ${depsWithoutCenter.length} departments to center "${firstCenter.name}"`);
      }
    }
  } catch (error) {
    log(`Error in ensureDefaultCentersExist: ${error instanceof Error ? error.message : String(error)}`);
  }
}

(async () => {
  const server = createServer(app);
  await registerRoutes(app);
  
  await runSchemaMigrations();
  await ensureDefaultCentersExist();

  // Set up WebSocket server with path to avoid conflict with Vite
  const wss = new WebSocketServer({ 
    server,
    path: '/ws'
  });
  
  wss.on('connection', (ws, req) => {
    const url = req.url;
    log(`WebSocket client connected from: ${url}`);
    
    ws.on('message', (message) => {
      try {
        const data = JSON.parse(message.toString());
        
        if (data.type === 'auth' && data.userId) {
          // Store the connection with user ID
          wsConnections.set(String(data.userId), ws);
          log(`User ${data.userId} authenticated via WebSocket`);
          
          ws.send(JSON.stringify({
            type: 'auth_success',
            message: 'Successfully authenticated'
          }));
        }
      } catch (error) {
        log(`Error parsing WebSocket message: ${error instanceof Error ? error.message : String(error)}`);
      }
    });
    
    ws.on('close', () => {
      // Remove connection when client disconnects
      for (const [userId, connection] of Array.from(wsConnections.entries())) {
        if (connection === ws) {
          wsConnections.delete(userId);
          log(`User ${userId} WebSocket disconnected`);
          break;
        }
      }
    });
    
    ws.on('error', (error) => {
      log(`WebSocket error: ${error.message}`);
    });
  });

  app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    const status = err.status || err.statusCode || 500;
    const message = err.message || "Internal Server Error";

    res.status(status).json({ message });
    throw err;
  });

  // importantly only setup vite in development and after
  // setting up all the other routes so the catch-all route
  // doesn't interfere with the other routes
  if (app.get("env") === "development") {
    await setupVite(app, server);
  } else {
    serveStatic(app);
  }

  // ALWAYS serve the app on the port specified in the environment variable PORT
  // Other ports are firewalled. Default to 5000 if not specified.
  // this serves both the API and the client.
  // It is the only port that is not firewalled.
  const port = parseInt(process.env.PORT || '5000', 10);
  server.listen(port, "0.0.0.0", () => {
    log(`serving on port ${port}`);
  });
})();
