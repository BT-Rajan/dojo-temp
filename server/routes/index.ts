import type { Express } from "express";
import { createServer, type Server } from "http";
import { setupAuth } from "../replitAuth";
import { setupLocalAuth } from "../localAuth";

import { registerAuthRoutes } from "./auth";
import { registerCentersRoutes } from "./centers";
import { registerDepartmentsRoutes } from "./departments";
import { registerAdminRoutes } from "./admin";
import { registerSettingsRoutes } from "./settings";
import { registerControlCenterRoutes } from "./control-center";
import { registerDoctorsRoutes } from "./doctors";
import { registerClinicsRoutes } from "./clinics";
import { registerLeavesRoutes } from "./leaves";
import { registerPermissionsRoutes } from "./permissions";
import { registerEmergencyRoutes } from "./emergency";
import { registerExaminationRoutes } from "./examination";
import { registerDashboardRoutes } from "./dashboard";
import { registerDoctorAuthRoutes } from "./doctor-auth";
import { registerAppointmentsRoutes } from "./appointments";
import { registerPatientsRoutes } from "./patients";
import { registerProceduresRoutes } from "./procedures";
import { registerDoctorAvailabilityRoutes } from "./doctor-availability";
import { registerOvertimeRoutes } from "./overtime";
import { registerExamScheduleRoutes } from "./exam-schedule";

// Registration order matches the original monolithic routes.ts exactly, so
// any two handlers registered for the same method+path keep resolving to
// whichever was registered first, same as before this file was split up.
export async function registerRoutes(app: Express): Promise<Server> {
  // Auth middleware
  await setupAuth(app);
  setupLocalAuth(app);

  registerAuthRoutes(app);
  registerCentersRoutes(app);
  registerDepartmentsRoutes(app);
  registerAdminRoutes(app);
  registerSettingsRoutes(app);
  registerControlCenterRoutes(app);
  registerDoctorsRoutes(app);
  registerClinicsRoutes(app);
  registerLeavesRoutes(app);
  registerPermissionsRoutes(app);
  registerEmergencyRoutes(app);
  registerExaminationRoutes(app);
  registerDashboardRoutes(app);
  registerDoctorAuthRoutes(app);
  registerAppointmentsRoutes(app);
  registerPatientsRoutes(app);
  registerProceduresRoutes(app);
  registerDoctorAvailabilityRoutes(app);
  registerOvertimeRoutes(app);
  registerExamScheduleRoutes(app);

  const httpServer = createServer(app);
  return httpServer;
}
