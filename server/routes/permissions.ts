import type { Express } from "express";
import { storage } from "../storage";
import { insertPermissionSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerPermissionsRoutes(app: Express): void {
  // Permission routes (department-specific)
  app.get("/api/permissions", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId } = req.query;
      if (departmentId) {
        const permissions = await storage.getPermissionsByDepartment(parseInt(departmentId));
        res.json(permissions);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const permissions = await storage.getPermissions();
          res.json(permissions);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch permissions" });
    }
  });

  app.get("/api/permissions/month/:year/:month", isAuthenticated, async (req: any, res) => {
    try {
      const year = parseInt(req.params.year);
      const month = parseInt(req.params.month);
      const { departmentId } = req.query;

      if (departmentId) {
        const permissions = await storage.getPermissionsByMonthAndDepartment(year, month, parseInt(departmentId));
        res.json(permissions);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const permissions = await storage.getPermissionsByMonth(year, month);
          res.json(permissions);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch permissions" });
    }
  });

  app.post("/api/permissions", isAuthenticated, async (req, res) => {
    try {
      console.log("Permission creation request body:", req.body);
      const permissionData = insertPermissionSchema.parse(req.body);
      console.log("Parsed permission data:", permissionData);
      const permission = await storage.createPermission(permissionData);
      res.status(201).json(permission);
    } catch (error) {
      console.error("Permission creation error:", error);
      if (error instanceof z.ZodError) {
        console.error("Zod validation errors:", error.errors);
        return res.status(400).json({ message: "Invalid permission data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create permission" });
    }
  });

  app.patch("/api/permissions/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const permissionData = insertPermissionSchema.partial().parse(req.body);
      const permission = await storage.updatePermission(id, permissionData);
      res.json(permission);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid permission data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update permission" });
    }
  });

  // Clear all permissions - MUST be before the :id route
  app.delete("/api/permissions/clear", isAuthenticated, async (req, res) => {
    try {
      console.log("Attempting to clear all permissions...");
      await storage.clearAllPermissions();
      console.log("Successfully cleared all permissions");
      res.status(204).send();
    } catch (error) {
      console.error("Error clearing permissions in route:", error);
      res.status(500).json({ message: "Failed to clear all permissions" });
    }
  });

  app.delete("/api/permissions/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      console.log(`Attempting to delete permission with id: ${req.params.id} (parsed: ${id})`);

      // Check if id is valid integer
      if (isNaN(id)) {
        return res.status(400).json({ message: "Invalid permission ID" });
      }

      await storage.deletePermission(id);
      res.status(204).send();
    } catch (error) {
      console.error("Error deleting permission:", error);
      res.status(500).json({ message: "Failed to delete permission" });
    }
  });

  app.delete("/api/permissions", isAuthenticated, async (req, res) => {
    try {
      await storage.clearAllPermissions();
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to clear permissions" });
    }
  });

}
