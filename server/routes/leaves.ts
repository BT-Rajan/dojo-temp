import type { Express } from "express";
import { storage } from "../storage";
import { insertLeaveSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerLeavesRoutes(app: Express): void {
  // Leave routes (department-specific)
  app.get("/api/leaves", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      if (departmentId) {
        const leaves = await storage.getLeavesByDepartment(parseInt(departmentId));
        res.json(leaves);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const leaves = await storage.getLeaves();
          res.json(leaves);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch leaves" });
    }
  });

  app.get("/api/leaves/active", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      if (departmentId) {
        const leaves = await storage.getActiveLeavesByDepartment(parseInt(departmentId));
        res.json(leaves);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const leaves = await storage.getActiveLeaves();
          res.json(leaves);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch active leaves" });
    }
  });

  app.post("/api/leaves", isAuthenticated, async (req, res) => {
    try {
      const leaveData = insertLeaveSchema.parse(req.body);
      const leave = await storage.createLeave(leaveData);
      res.status(201).json(leave);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid leave data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create leave" });
    }
  });

  app.put("/api/leaves/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const leaveData = insertLeaveSchema.partial().parse(req.body);
      const leave = await storage.updateLeave(id, leaveData);
      res.json(leave);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid leave data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update leave" });
    }
  });

  app.patch("/api/leaves/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const leaveData = insertLeaveSchema.partial().parse(req.body);
      const leave = await storage.updateLeave(id, leaveData);
      res.json(leave);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid leave data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update leave" });
    }
  });

  app.delete("/api/leaves/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteLeave(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete leave" });
    }
  });

}
