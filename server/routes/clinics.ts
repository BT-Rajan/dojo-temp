import type { Express } from "express";
import { storage } from "../storage";
import { insertClinicSchema, insertClinicAssignmentSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerClinicsRoutes(app: Express): void {
  // Clinic routes (department-specific)
  app.get("/api/clinics", async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      const userId = req.user?.claims?.sub || req.user?.id;
      
      if (departmentId) {
        // Get clinics for specific department only
        const clinics = await storage.getClinicsByDepartment(parseInt(departmentId));
        res.json(clinics);
      } else {
        // If no department specified, get all clinics (for center heads only)
        const user = await storage.getUser(userId);
        if (user?.isCenterHead) {
          const clinics = await storage.getClinics();
          res.json(clinics);
        } else {
          res.json([]); // Regular users need to specify department
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch clinics" });
    }
  });
  
  app.post("/api/clinics", isAuthenticated, async (req: any, res) => {
    try {
      const clinicData = insertClinicSchema.parse(req.body);
      const userId = req.user?.claims?.sub || req.user?.id;
      
      // Ensure department is specified and user has access to it
      if (!clinicData.departmentId) {
        return res.status(400).json({ message: "Department is required" });
      }
      
      // Check if user has permission to add clinics to this department
      const canEdit = await storage.canUserEditDepartment(userId, clinicData.departmentId);
      console.log(`User ${userId} trying to add clinic to department ${clinicData.departmentId}: canEdit = ${canEdit}`);
      if (!canEdit) {
        return res.status(403).json({ message: "Insufficient permissions for this department" });
      }
      
      const clinic = await storage.createClinic(clinicData);
      res.status(201).json(clinic);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid clinic data", errors: error.errors });
      }
      console.error("Create clinic error:", error);
      res.status(500).json({ message: "Failed to create clinic" });
    }
  });
  
  app.put("/api/clinics/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const clinicData = insertClinicSchema.partial().parse(req.body);
      const clinic = await storage.updateClinic(id, clinicData);
      res.json(clinic);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid clinic data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update clinic" });
    }
  });
  
  app.delete("/api/clinics/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteClinic(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete clinic" });
    }
  });
  
  // Clinic assignment routes (supports both doctor and department filtering)
  app.get("/api/clinic-assignments", isAuthenticated, async (req: any, res) => {
    try {
      const { doctorId, departmentId } = req.query;
      console.log(`Clinic assignments request - doctorId: ${doctorId}, departmentId: ${departmentId}, all query params:`, req.query);

      if (doctorId) {
        // Get assignments for specific doctor only
        console.log(`Fetching clinic assignments for doctor ID: ${doctorId}`);
        const assignments = await storage.getClinicAssignmentsByDoctor(parseInt(doctorId as string));
        console.log(`Found ${assignments.length} assignments for doctor ${doctorId}:`, assignments.map(a => ({ id: a.id, doctorId: a.doctorId, weekday: a.weekday, clinic: a.clinic?.name })));
        res.json(assignments);
        return;
      } else if (departmentId) {
        // Get assignments for specific department
        console.log(`Fetching clinic assignments for department ID: ${departmentId}`);
        const assignments = await storage.getClinicAssignmentsByDepartment(parseInt(departmentId as string));
        res.json(assignments);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          console.log(`No doctorId or departmentId provided, returning all assignments`);
          const assignments = await storage.getClinicAssignments();
          res.json(assignments);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      console.error('Error fetching clinic assignments:', error);
      res.status(500).json({ message: "Failed to fetch clinic assignments" });
    }
  });

  app.get("/api/clinic-assignments/weekday/:weekday", isAuthenticated, async (req: any, res) => {
    try {
      const weekday = parseInt(req.params.weekday);
      const { departmentId } = req.query;

      if (departmentId) {
        const assignments = await storage.getClinicAssignmentsByWeekdayAndDepartment(weekday, parseInt(departmentId));
        res.json(assignments);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const assignments = await storage.getClinicAssignmentsByWeekday(weekday);
          res.json(assignments);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch clinic assignments" });
    }
  });

  app.post("/api/clinic-assignments", isAuthenticated, async (req, res) => {
    try {
      const assignmentData = insertClinicAssignmentSchema.parse(req.body);
      const assignment = await storage.createClinicAssignment(assignmentData);
      res.status(201).json(assignment);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid assignment data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create clinic assignment" });
    }
  });
  
  app.delete("/api/clinic-assignments/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteClinicAssignment(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete clinic assignment" });
    }
  });
  
}
