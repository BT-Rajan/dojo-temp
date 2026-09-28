import type { Express } from "express";
import { storage } from "../storage";
import { z } from "zod";

export function registerDashboardRoutes(app: Express): void {
  // Dashboard routes (department-specific)
  app.get("/api/dashboard/stats", async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      if (departmentId) {
        const stats = await storage.getDashboardStatsByDepartment(parseInt(departmentId));
        res.json(stats);
      } else {
        const stats = await storage.getDashboardStats();
        res.json(stats);
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch dashboard stats" });
    }
  });
  
}
