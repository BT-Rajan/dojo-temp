import type { Express } from "express";
import { storage } from "../storage";
import { createDoctorAccountSchema, doctorLoginSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";
import { hashPassword } from "../localAuth";

export function registerDoctorAuthRoutes(app: Express): void {
  // Doctor authentication routes
  app.post("/api/doctor/create-account", isAuthenticated, async (req, res) => {
    try {
      const { doctorId, username, password } = createDoctorAccountSchema.parse(req.body);
      const passwordHash = await hashPassword(password);
      const doctor = await storage.createDoctorAccount(doctorId, username, passwordHash);
      res.status(201).json({ success: true, doctor: { id: doctor.id, name: doctor.name, username: doctor.username } });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid account data", errors: error.errors });
      }
      console.error("Create doctor account error:", error);
      res.status(500).json({ message: "Failed to create doctor account" });
    }
  });
  
  app.post("/api/doctor/login", async (req, res) => {
    try {
      const { username, password } = doctorLoginSchema.parse(req.body);
      const doctor = await storage.getDoctorByUsername(username);
      
      if (!doctor || !doctor.passwordHash) {
        return res.status(401).json({ message: "Invalid credentials" });
      }
  
      const bcrypt = await import("bcryptjs");
      const isValidPassword = await bcrypt.compare(password, doctor.passwordHash);
      
      if (!isValidPassword) {
        return res.status(401).json({ message: "Invalid credentials" });
      }
  
      await storage.updateDoctorLogin(doctor.id);
  
      // Create a proper session for the doctor
      const doctorUser = {
        id: `doctor_${doctor.id}`,
        doctorId: doctor.id,
        username: doctor.username,
        isDoctor: true,
        isLocalAccount: true,
        name: doctor.name,
        title: doctor.title,
        departmentId: doctor.departmentId,
        email: doctor.email,
        phone: doctor.phone
      };
  
      req.logIn(doctorUser, (err: any) => {
        if (err) {
          console.error('Doctor login error:', err);
          return res.status(500).json({ message: "Failed to establish session" });
        }
        
        res.json({
          success: true,
          doctor: {
            id: doctor.id,
            name: doctor.name,
            title: doctor.title,
            departmentId: doctor.departmentId,
            email: doctor.email,
            phone: doctor.phone
          }
        });
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid login data", errors: error.errors });
      }
      console.error("Doctor login error:", error);
      res.status(500).json({ message: "Login failed" });
    }
  });
  
  // Doctor logout route
  app.post("/api/doctor/logout", (req, res) => {
    req.logout((err) => {
      if (err) {
        return res.status(500).json({ message: "Failed to logout" });
      }
      res.json({ message: "Logged out successfully" });
    });
  });
  
  // Get current doctor information for OIDC or traditional login
  app.get("/api/doctor/current", isAuthenticated, async (req: any, res) => {
    try {
      console.log("=== /api/doctor/current DEBUG ===");
      console.log("req.user:", JSON.stringify(req.user, null, 2));
      console.log("req.user.claims:", req.user?.claims);
      
      const userId = req.user.claims?.sub || req.user.id;
      console.log("Extracted userId:", userId);
      
      // Check if user is already a doctor (traditional login)
      if (req.user.isDoctor && req.user.doctorId) {
        console.log("Traditional doctor login detected, doctorId:", req.user.doctorId);
        const doctor = await storage.getDoctor(req.user.doctorId);
        return res.json(doctor);
      }
      
      // For OIDC users, try to find doctor by mapping (temporary solution)
      // This is a temporary mapping - in production you'd have a proper user-to-doctor mapping
      const user = await storage.getUser(userId);
      console.log("Found user in database:", user ? `${user.email} (${user.id})` : "null");
      
      // For OIDC users, we can work directly with claims even if no user record exists
      let userEmail = user?.email || req.user.claims?.email;
      console.log("Using email for doctor matching:", userEmail);
      
      if (userEmail) {
        // Match the OIDC user to their doctor record by email. This used to
        // fall back to "the first doctor in the system" when no email
        // matched, which silently logged an OIDC user in as an arbitrary
        // doctor — an identity-confusion bug, not just a missing mapping —
        // so that fallback has been removed. Add a proper userId-to-doctor
        // mapping (see TODO above) rather than reintroducing a fallback here.
        const doctors = await storage.getDoctors();
        const doctor = doctors.find(d => d.email === userEmail);
        console.log("Email match doctor:", doctor ? `${doctor.name} (${doctor.id})` : "null");

        if (doctor) {
          console.log(`Returning doctor: ${doctor.name} (ID: ${doctor.id})`);
          return res.json(doctor);
        }
      }
      
      console.log("No doctor mapping found, returning 404");
      res.status(404).json({ message: "No doctor profile found for current user" });
    } catch (error) {
      console.error("Error fetching current doctor:", error);
      res.status(500).json({ message: "Failed to fetch doctor information" });
    }
  });
  
  // Doctor appointment scheduling
}
