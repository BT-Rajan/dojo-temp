import type { Express } from "express";
import { storage } from "../storage";
import { insertDoctorAvailabilitySchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerDoctorAvailabilityRoutes(app: Express): void {
  // Doctor availability routes
  app.get("/api/doctor-availability/:doctorId", async (req, res) => {
    try {
      const doctorId = parseInt(req.params.doctorId);
      const availability = await storage.getDoctorAvailability(doctorId);
      res.json(availability);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch doctor availability" });
    }
  });
  
  app.post("/api/doctor-availability", isAuthenticated, async (req, res) => {
    try {
      const availabilityData = insertDoctorAvailabilitySchema.parse(req.body);
      const availability = await storage.createDoctorAvailability(availabilityData);
      res.status(201).json(availability);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid availability data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create doctor availability" });
    }
  });
  
  app.put("/api/doctor-availability/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const availabilityData = insertDoctorAvailabilitySchema.partial().parse(req.body);
      const availability = await storage.updateDoctorAvailability(id, availabilityData);
      res.json(availability);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid availability data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update doctor availability" });
    }
  });
  
  app.delete("/api/doctor-availability/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteDoctorAvailability(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete doctor availability" });
    }
  });
  
  // Doctor of the Month API endpoints
  app.get('/api/departments/:departmentId/doctor-of-month/awards', async (req, res) => {
    try {
      const departmentId = parseInt(req.params.departmentId);
      const awards = await storage.getDoctorOfTheMonthAwards(departmentId);
      res.json(awards);
    } catch (error) {
      console.error("Error fetching doctor of the month awards:", error);
      res.status(500).json({ message: "Failed to fetch awards" });
    }
  });
  
  app.get('/api/departments/:departmentId/doctor-of-month/current', async (req, res) => {
    try {
      const departmentId = parseInt(req.params.departmentId);
      const now = new Date();
      const currentMonth = now.getMonth() + 1; // JavaScript months are 0-based
      const currentYear = now.getFullYear();
      
      const currentAward = await storage.getDoctorOfTheMonthForPeriod(departmentId, currentYear, currentMonth);
      res.json(currentAward);
    } catch (error) {
      console.error("Error fetching current doctor of the month:", error);
      res.status(500).json({ message: "Failed to fetch current award" });
    }
  });
  
  app.get('/api/departments/:departmentId/doctor-rankings/:year/:month', async (req, res) => {
    try {
      const departmentId = parseInt(req.params.departmentId);
      const year = parseInt(req.params.year);
      const month = parseInt(req.params.month);
      
      const rankings = await storage.calculateMonthlyDoctorRankings(departmentId, year, month);
      res.json(rankings);
    } catch (error) {
      console.error("Error calculating doctor rankings:", error);
      res.status(500).json({ message: "Failed to calculate rankings" });
    }
  });
  
  app.post('/api/departments/:departmentId/doctor-of-month/award', async (req, res) => {
    try {
      const departmentId = parseInt(req.params.departmentId);
      const { doctorId, year, month } = req.body;
      
      // Get the doctor's performance data
      const rankings = await storage.calculateMonthlyDoctorRankings(departmentId, year, month);
      const doctorRanking = rankings.find(r => r.doctorId === doctorId);
      
      if (!doctorRanking) {
        return res.status(404).json({ message: "Doctor not found in rankings" });
      }
      
      // Create the award
      const awardData = {
        doctorId,
        departmentId,
        year,
        month,
        totalAppointments: doctorRanking.totalAppointments,
        completedAppointments: doctorRanking.completedAppointments,
        completionRate: doctorRanking.completionRate,
        patientSatisfactionScore: 0, // Placeholder
        punctualityScore: 0, // Placeholder
        overallScore: doctorRanking.overallScore,
        certificateGenerated: false,
        certificateUrl: null,
      };
      
      const newAward = await storage.createDoctorOfTheMonthAward(awardData);
      res.json(newAward);
    } catch (error) {
      console.error("Error creating doctor of the month award:", error);
      res.status(500).json({ message: "Failed to create award" });
    }
  });
  
}
