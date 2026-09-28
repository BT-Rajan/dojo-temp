import type { Express } from "express";
import { storage } from "../storage";
import { insertExaminationSlotSchema, insertExaminationAssignmentSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerExaminationRoutes(app: Express): void {
  // Examination slot routes (department-specific)
  app.get("/api/examination-slots", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      if (departmentId) {
        const slots = await storage.getExaminationSlotsByDepartment(parseInt(departmentId));
        res.json(slots);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const slots = await storage.getExaminationSlots();
          res.json(slots);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch examination slots" });
    }
  });

  app.get("/api/examination-slots/weekday/:weekday", isAuthenticated, async (req: any, res) => {
    try {
      const weekday = parseInt(req.params.weekday);
      const { departmentId } = req.query;

      if (departmentId) {
        const slots = await storage.getExaminationSlotsByWeekdayAndDepartment(weekday, parseInt(departmentId));
        res.json(slots);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const slots = await storage.getExaminationSlotsByWeekday(weekday);
          res.json(slots);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch examination slots" });
    }
  });

  app.post("/api/examination-slots", isAuthenticated, async (req: any, res) => {
    try {
      const slotData = insertExaminationSlotSchema.parse(req.body);
      const userId = req.user?.claims?.sub || req.user?.id;

      // Ensure department is specified and user has access to it
      if (!slotData.departmentId) {
        return res.status(400).json({ message: "Department is required" });
      }

      // Check if user has permission to add examination slots to this department
      const canEdit = await storage.canUserEditDepartment(userId, slotData.departmentId);
      console.log(`User ${userId} trying to add examination slot to department ${slotData.departmentId}: canEdit = ${canEdit}`);
      if (!canEdit) {
        return res.status(403).json({ message: "Insufficient permissions for this department" });
      }

      const slot = await storage.createExaminationSlot(slotData);
      res.status(201).json(slot);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid slot data", errors: error.errors });
      }
      console.error("Create examination slot error:", error);
      res.status(500).json({ message: "Failed to create examination slot" });
    }
  });

  app.put("/api/examination-slots/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const slotData = insertExaminationSlotSchema.partial().parse(req.body);
      const slot = await storage.updateExaminationSlot(id, slotData);
      res.json(slot);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid slot data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update examination slot" });
    }
  });

  app.delete("/api/examination-slots/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteExaminationSlot(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete examination slot" });
    }
  });

  // Examination assignment routes
  app.get("/api/examination-assignments", isAuthenticated, async (req, res) => {
    try {
      const assignments = await storage.getExaminationAssignments();
      res.json(assignments);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch examination assignments" });
    }
  });

  app.post("/api/examination-assignments", isAuthenticated, async (req, res) => {
    try {
      const assignmentData = insertExaminationAssignmentSchema.parse(req.body);
      const assignment = await storage.createExaminationAssignment(assignmentData);
      res.status(201).json(assignment);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid assignment data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create examination assignment" });
    }
  });

  app.delete("/api/examination-assignments/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteExaminationAssignment(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete examination assignment" });
    }
  });

}
