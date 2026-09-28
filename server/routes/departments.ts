import type { Express } from "express";
import { storage } from "../storage";
import { insertDepartmentSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerDepartmentsRoutes(app: Express): void {
  // Department routes
  app.get("/api/departments", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user?.claims?.sub || req.user?.id;
      const currentUser = await storage.getUser(userId);
      if (currentUser?.isCenterHead) {
        const departments = await storage.getDepartments();
        res.json(departments);
      } else {
        // Non-center-heads only see the departments they belong to —
        // use /api/user/departments?centerId=X for center-scoped access.
        const departments = await storage.getUserDepartments(userId);
        res.json(departments);
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch departments" });
    }
  });
  
  app.get("/api/user/departments", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims?.sub || req.user.id;
      const centerId = req.query.centerId ? parseInt(req.query.centerId as string) : undefined;
      if (centerId) {
        const depts = await storage.getDepartmentsByCenter(centerId);
        const userDepts = await storage.getUserDepartments(userId);
        const userDeptIds = new Set(userDepts.map(d => d.id));
        const user = await storage.getUser(userId);
        if (user?.isCenterHead) {
          res.json(depts);
        } else {
          res.json(depts.filter(d => userDeptIds.has(d.id)));
        }
      } else {
        const departments = await storage.getUserDepartments(userId);
        res.json(departments);
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch user departments" });
    }
  });
  
  app.post("/api/departments", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims?.sub || req.user.id;
      if (!req.body.centerId) {
        return res.status(400).json({ message: "Center ID is required when creating a department" });
      }
      const departmentData = insertDepartmentSchema.parse({
        ...req.body,
        headUserId: userId
      });
      const department = await storage.createDepartment(departmentData);
      
      // Add the creator as a member with head role
      await storage.addDepartmentMember({
        userId,
        departmentId: department.id,
        role: "head"
      });
      
      res.status(201).json(department);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid department data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create department" });
    }
  });
  
  app.get("/api/departments/:id/members", isAuthenticated, async (req, res) => {
    try {
      const departmentId = parseInt(req.params.id);
      const members = await storage.getDepartmentMembers(departmentId);
      res.json(members);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch department members" });
    }
  });
  
  // Add member to department
  app.post("/api/departments/:id/members", isAuthenticated, async (req: any, res) => {
    try {
      const departmentId = parseInt(req.params.id);
      const currentUserId = req.user.claims?.sub || req.user.id;
      const currentUser = await storage.getUser(currentUserId);
      
      // Check if current user can add members to this department
      if (!currentUser?.isCenterHead) {
        const members = await storage.getDepartmentMembers(departmentId);
        const currentUserMembership = members.find(m => m.userId === currentUserId);
        
        if (!currentUserMembership || currentUserMembership.role !== "head") {
          return res.status(403).json({ message: "Only department heads can add members" });
        }
      }
  
      // Validate the member data
      const memberData = z.object({
        userId: z.string(),
        departmentId: z.number(),
        role: z.enum(["head", "member", "viewer", "reception", "secretary"]),
        canEdit: z.boolean().optional().default(false),
        canViewOthers: z.boolean().optional().default(false),
        canAssignEmergencies: z.boolean().optional().default(false),
        canManageLeaves: z.boolean().optional().default(false),
        canViewReports: z.boolean().optional().default(false),
      }).parse({
        ...req.body,
        departmentId,
      });
  
      const member = await storage.addDepartmentMember(memberData);
      res.status(201).json(member);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid member data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to add department member" });
    }
  });
  
  // Update member role and permissions
  app.put("/api/departments/:id/members/:userId", isAuthenticated, async (req: any, res) => {
    try {
      const departmentId = parseInt(req.params.id);
      const targetUserId = req.params.userId;
      const currentUserId = req.user.claims?.sub || req.user.id;
      const currentUser = await storage.getUser(currentUserId);
      
      // Check if current user can modify roles in this department
      if (!currentUser?.isCenterHead) {
        const members = await storage.getDepartmentMembers(departmentId);
        const currentUserMembership = members.find(m => m.userId === currentUserId);
        
        if (!currentUserMembership || currentUserMembership.role !== "head") {
          return res.status(403).json({ message: "Only department heads can modify member roles" });
        }
      }
  
      // Validate the update data
      const updateData = z.object({
        role: z.enum(["head", "member", "viewer", "reception", "secretary"]).optional(),
        canEdit: z.boolean().optional(),
        canViewOthers: z.boolean().optional(),
        canAssignEmergencies: z.boolean().optional(),
        canManageLeaves: z.boolean().optional(),
        canViewReports: z.boolean().optional(),
      }).parse(req.body);
  
      await storage.updateDepartmentMember(departmentId, targetUserId, updateData);
      
      res.json({ message: "Member permissions updated successfully" });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid update data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update member permissions" });
    }
  });
  
}
