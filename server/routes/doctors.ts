import type { Express } from "express";
import { storage } from "../storage";
import { insertDoctorSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerDoctorsRoutes(app: Express): void {
  // Doctor routes (department-specific)
  app.get("/api/doctors", async (req: any, res) => {
    try {
      const { departmentId, centerId } = req.query;
      const userId = req.user?.claims?.sub || req.user?.id;
      const currentUser = await storage.getUser(userId);
      
      if (departmentId) {
        const doctors = await storage.getDoctorsByDepartment(parseInt(departmentId));
        res.json(doctors);
      } else if (centerId) {
        if (!currentUser?.isCenterHead) {
          const userCenters = await storage.getUserCenters(userId);
          const isMember = userCenters.some(c => c.id === parseInt(centerId as string));
          if (!isMember) {
            return res.status(403).json({ message: "Access denied to this center" });
          }
        }
        const doctors = await storage.getDoctorsByCenter(parseInt(centerId as string));
        res.json(doctors);
      } else {
        if (currentUser?.isCenterHead) {
          const doctors = await storage.getDoctors();
          res.json(doctors);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch doctors" });
    }
  });
  
  app.get("/api/doctors/:id", async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const doctor = await storage.getDoctor(id);
      if (!doctor) {
        return res.status(404).json({ message: "Doctor not found" });
      }
      res.json(doctor);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch doctor" });
    }
  });
  
  app.post("/api/doctors", isAuthenticated, async (req: any, res) => {
    try {
      const doctorData = insertDoctorSchema.parse(req.body);
      const userId = req.user?.claims?.sub || req.user?.id;
      
      // Ensure department is specified and user has access to it
      if (!doctorData.departmentId) {
        return res.status(400).json({ message: "Department is required" });
      }
      
      // Check if user has permission to add doctors to this department
      const canEdit = await storage.canUserEditDepartment(userId, doctorData.departmentId);
      console.log(`User ${userId} trying to add doctor to department ${doctorData.departmentId}: canEdit = ${canEdit}`);
      if (!canEdit) {
        return res.status(403).json({ message: "Insufficient permissions for this department" });
      }
      
      const doctor = await storage.createDoctor(doctorData);
      res.status(201).json(doctor);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid doctor data", errors: error.errors });
      }
      console.error("Create doctor error:", error);
      res.status(500).json({ message: "Failed to create doctor" });
    }
  });
  
  app.put("/api/doctors/:id", async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const doctorData = insertDoctorSchema.partial().parse(req.body);
      const doctor = await storage.updateDoctor(id, doctorData);
      res.json(doctor);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid doctor data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update doctor" });
    }
  });
  
  app.delete("/api/doctors/:id", async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteDoctor(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete doctor" });
    }
  });
  
}
