import type { Express } from "express";
import { storage } from "../storage";
import { z } from "zod";
import { requireCenterHead } from "../localAuth";

export function registerControlCenterRoutes(app: Express): void {
  // Control Center Routes (accessible to Center Heads only)
  app.get("/api/control-center/departments/:weekday", requireCenterHead, async (req: any, res) => {
    try {
      const { weekday } = req.params;
      const departments = await storage.getDepartmentsWithTodaysClinics(weekday);
      res.json(departments);
    } catch (error) {
      console.error("Control center departments error:", error);
      res.status(500).json({ message: "Failed to fetch departments with clinics" });
    }
  });
  
  app.get("/api/control-center/permissions/:date", requireCenterHead, async (req: any, res) => {
    try {
      const { date } = req.params;
      const permissions = await storage.getPermissionsByDate(date);
      res.json(permissions);
    } catch (error) {
      console.error("Control center permissions error:", error);
      res.status(500).json({ message: "Failed to fetch permissions" });
    }
  });
  
  app.get("/api/control-center/leaves/active", requireCenterHead, async (req: any, res) => {
    try {
      const leaves = await storage.getActiveLeaves();
      res.json(leaves);
    } catch (error) {
      console.error("Control center active leaves error:", error);
      res.status(500).json({ message: "Failed to fetch active leaves" });
    }
  });
  
}
