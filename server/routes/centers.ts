import type { Express } from "express";
import { storage } from "../storage";
import { insertCenterSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";
import { requireCenterHead } from "../localAuth";

export function registerCentersRoutes(app: Express): void {
  // Center routes
  app.get("/api/centers", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims?.sub || req.user.id;
      const user = await storage.getUser(userId);
      if (user?.isCenterHead) {
        const allCenters = await storage.getCenters();
        res.json(allCenters);
      } else {
        const userCenters = await storage.getUserCenters(userId);
        res.json(userCenters);
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch centers" });
    }
  });
  
  app.get("/api/user/centers", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims?.sub || req.user.id;
      const userCenters = await storage.getUserCenters(userId);
      res.json(userCenters);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch user centers" });
    }
  });
  
  app.post("/api/centers", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims?.sub || req.user.id;
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        return res.status(403).json({ message: "Only center heads can create centers" });
      }
      const centerData = insertCenterSchema.parse({
        ...req.body,
        createdBy: userId,
      });
      const center = await storage.createCenter(centerData);
      await storage.addCenterMember({ centerId: center.id, userId, role: "admin" });
      res.status(201).json(center);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid center data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create center" });
    }
  });
  
  app.put("/api/centers/:id", isAuthenticated, async (req: any, res) => {
    try {
      const centerId = parseInt(req.params.id);
      const userId = req.user.claims?.sub || req.user.id;
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        return res.status(403).json({ message: "Only center heads can update centers" });
      }
      const center = await storage.updateCenter(centerId, req.body);
      res.json(center);
    } catch (error) {
      res.status(500).json({ message: "Failed to update center" });
    }
  });
  
  app.delete("/api/centers/:id", requireCenterHead, async (req, res) => {
    try {
      const centerId = parseInt(req.params.id);
      await storage.deleteCenter(centerId);
      res.json({ message: "Center deactivated successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to delete center" });
    }
  });
  
  app.get("/api/centers/:id/members", isAuthenticated, async (req, res) => {
    try {
      const centerId = parseInt(req.params.id);
      const members = await storage.getCenterMembers(centerId);
      res.json(members);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch center members" });
    }
  });
  
  app.post("/api/centers/:id/members", requireCenterHead, async (req: any, res) => {
    try {
      const centerId = parseInt(req.params.id);
      const member = await storage.addCenterMember({
        centerId,
        userId: req.body.userId,
        role: req.body.role || "member",
      });
      res.status(201).json(member);
    } catch (error) {
      res.status(500).json({ message: "Failed to add center member" });
    }
  });
  
  app.delete("/api/centers/:id/members/:userId", requireCenterHead, async (req, res) => {
    try {
      const centerId = parseInt(req.params.id);
      await storage.removeCenterMember(req.params.userId, centerId);
      res.json({ message: "Member removed from center" });
    } catch (error) {
      res.status(500).json({ message: "Failed to remove center member" });
    }
  });
  
  app.get("/api/centers/:id/departments", isAuthenticated, async (req, res) => {
    try {
      const centerId = parseInt(req.params.id);
      const depts = await storage.getDepartmentsByCenter(centerId);
      res.json(depts);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch center departments" });
    }
  });
  
}
