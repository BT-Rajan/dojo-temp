import type { Express } from "express";
import { storage } from "../storage";
import { updateCenterNameSchema } from "@shared/schema";
import { z } from "zod";
import { requireCenterHead } from "../localAuth";

export function registerSettingsRoutes(app: Express): void {
  // System settings routes
  app.get("/api/settings/center-name", async (req, res) => {
    try {
      const setting = await storage.getSystemSetting("centerName");
      res.json({ centerName: setting?.value || "Medical Center" });
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch center name" });
    }
  });
  
  app.put("/api/settings/center-name", requireCenterHead, async (req: any, res) => {
    try {
      const { centerName } = updateCenterNameSchema.parse(req.body);
      const userId = req.user.claims?.sub || req.user.id;
      
      await storage.setSystemSetting(
        "centerName", 
        centerName, 
        "Medical center name displayed throughout the application",
        userId
      );
      
      res.json({ message: "Center name updated successfully", centerName });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid center name", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update center name" });
    }
  });
  
}
