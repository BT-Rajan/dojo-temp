import type { Express } from "express";
import { storage } from "../storage";
import { insertEmergencyAssignmentSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";
import { requireCenterHead } from "../localAuth";

export function registerEmergencyRoutes(app: Express): void {
  // Emergency assignment routes (department-specific)
  app.get("/api/emergency-assignments", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      if (departmentId) {
        const assignments = await storage.getEmergencyAssignmentsByDepartment(parseInt(departmentId));
        res.json(assignments);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const assignments = await storage.getEmergencyAssignments();
          res.json(assignments);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch emergency assignments" });
    }
  });

  app.get("/api/emergency-assignments/month/:year/:month", isAuthenticated, async (req: any, res) => {
    try {
      const year = parseInt(req.params.year);
      const month = parseInt(req.params.month);
      const { departmentId } = req.query;

      if (departmentId) {
        const assignments = await storage.getEmergencyAssignmentsByMonthAndDepartment(year, month, parseInt(departmentId));
        res.json(assignments);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const assignments = await storage.getEmergencyAssignmentsByMonth(year, month);
          res.json(assignments);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch emergency assignments" });
    }
  });

  app.get("/api/emergency-assignments/next-doctor", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId, skipDoctorIds } = req.query;
      const skipIds = skipDoctorIds ?
        (skipDoctorIds as string).split(',').map(id => parseInt(id)).filter(id => !isNaN(id)) :
        [];

      console.log(`[Emergency] Getting next doctor - departmentId: ${departmentId}, skipIds: ${JSON.stringify(skipIds)}`);

      let doctor;

      if (departmentId) {
        doctor = await storage.getNextEmergencyDoctorByDepartment(parseInt(departmentId), skipIds);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (!currentUser?.isCenterHead) {
          return res.status(400).json({ message: "departmentId is required" });
        }
        doctor = await storage.getNextEmergencyDoctor();
      }

      if (!doctor) {
        console.log(`[Emergency] No available doctor found for department ${departmentId}`);
        return res.status(404).json({ message: "No available doctor for emergency assignment. Please ensure doctors have clinic assignments for today." });
      }
      
      console.log(`[Emergency] Returning doctor: ${doctor.name} (ID: ${doctor.id}), clinic: ${(doctor as any).currentClinic?.name || 'none'}`);
      res.json(doctor);
    } catch (error) {
      console.error("[Emergency] Error getting next doctor:", error);
      res.status(500).json({ message: "Failed to get next emergency doctor. Please try again." });
    }
  });
  
  app.get("/api/emergency-assignments/stats", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      let stats;

      if (departmentId) {
        stats = await storage.getEmergencyAssignmentStatsByDepartment(parseInt(departmentId));
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        stats = currentUser?.isCenterHead ? await storage.getEmergencyAssignmentStats() : [];
      }
      res.json(stats);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch emergency assignment stats" });
    }
  });
  
  app.delete("/api/emergency-assignments/clear", requireCenterHead, async (req, res) => {
    try {
      await storage.clearAllEmergencyAssignments();
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to clear emergency assignments" });
    }
  });
  
  app.post("/api/emergency-assignments", isAuthenticated, async (req: any, res) => {
    try {
      console.log("[Emergency POST] Received body:", JSON.stringify(req.body));
      const assignmentData = insertEmergencyAssignmentSchema.parse(req.body);
      
      // Get the doctor to determine department
      const doctor = await storage.getDoctor(assignmentData.doctorId);
      if (!doctor || !doctor.departmentId) {
        return res.status(400).json({ message: "Invalid doctor or doctor has no department" });
      }
  
      // Check emergency assignment permissions for this department
      const userId = req.user.claims?.sub || req.user.id;
      const user = await storage.getUser(userId);
      
      if (!user?.isCenterHead) {
        const members = await storage.getDepartmentMembers(doctor.departmentId);
        const userMembership = members.find(m => m.userId === userId);
        
        if (!userMembership) {
          return res.status(403).json({ message: "No access to this department" });
        }
  
        if (!userMembership.canAssignEmergencies && userMembership.role !== "head") {
          return res.status(403).json({ message: "No emergency assignment permissions" });
        }
      }
  
      const assignment = await storage.createEmergencyAssignment(assignmentData);
      res.status(201).json(assignment);
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.log("[Emergency POST] Zod validation errors:", JSON.stringify(error.errors));
        return res.status(400).json({ message: "Invalid assignment data", errors: error.errors });
      }
      console.error("[Emergency POST] Error:", error);
      res.status(500).json({ message: "Failed to create emergency assignment" });
    }
  });
  
}
