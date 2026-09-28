import type { Express } from "express";
import { storage } from "../storage";
import { insertDepartmentSchema, createLocalUserSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";
import { requireCenterHead, hashPassword } from "../localAuth";

export function registerAdminRoutes(app: Express): void {
  // Center Head Routes - User Management
  app.post("/api/admin/users", requireCenterHead, async (req: any, res) => {
    try {
      const userData = createLocalUserSchema.parse(req.body);
      const passwordHash = await hashPassword(userData.password);
      
      const user = await storage.createLocalUser({
        username: userData.username,
        passwordHash,
        firstName: userData.firstName,
        lastName: userData.lastName,
        email: userData.email,
        isCenterHead: userData.isCenterHead,
      });
  
      const creatorId = req.user.claims?.sub || req.user.id;
      const creatorCenters = await storage.getUserCenters(creatorId);
      for (const center of creatorCenters) {
        try {
          await storage.addCenterMember({ centerId: center.id, userId: user.id, role: "member" });
        } catch (e) {}
      }
      
      // Don't return password hash
      const { passwordHash: _, ...userResponse } = user;
      res.status(201).json(userResponse);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid user data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create user" });
    }
  });
  
  app.get("/api/admin/users", requireCenterHead, async (req, res) => {
    try {
      const centerId = req.query.centerId ? parseInt(req.query.centerId as string) : undefined;
      let usersList;
      if (centerId) {
        usersList = await storage.getUsersByCenter(centerId);
      } else {
        usersList = await storage.getAllUsers();
      }
      const sanitizedUsers = usersList.map(({ passwordHash, ...user }) => user);
      res.json(sanitizedUsers);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch users" });
    }
  });
  
  // Department Head Routes - Department Management
  app.put("/api/departments/:id", isAuthenticated, async (req: any, res) => {
    try {
      const departmentId = parseInt(req.params.id);
      const userId = req.user.claims?.sub || req.user.id;
      const user = await storage.getUser(userId);
      
      // Check permissions: center head or department head
      if (!user?.isCenterHead) {
        const userDepartments = await storage.getUserDepartments(userId);
        const membershipInDept = userDepartments.find(dept => dept.id === departmentId);
        
        if (!membershipInDept || membershipInDept.headUserId !== userId) {
          return res.status(403).json({ message: "Only center heads or department heads can edit department info" });
        }
      }
      
      const departmentData = insertDepartmentSchema.partial().parse(req.body);
      const department = await storage.updateDepartment(departmentId, departmentData);
      res.json(department);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid department data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update department" });
    }
  });
  
  // Set department head permissions
  app.post("/api/admin/departments/:id/set-head", requireCenterHead, async (req, res) => {
    try {
      const departmentId = parseInt(req.params.id);
      const { userId } = req.body;
      
      // If userId is empty or unassigned, remove the head assignment
      if (!userId || userId === "" || userId === "unassigned") {
        await storage.updateDepartment(departmentId, { headUserId: null });
        res.json({ message: "Department head removed successfully" });
        return;
      }
      
      // Update department head
      await storage.updateDepartment(departmentId, { headUserId: userId });
      
      // Update membership permissions
      await storage.removeDepartmentMember(userId, departmentId); // Remove if exists
      await storage.addDepartmentMember({
        userId,
        departmentId,
        role: "head",
        canEdit: true,
        canViewOthers: true,
      });
      
      res.json({ message: "Department head assigned successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to assign department head" });
    }
  });
  
  // Update Center Head status
  app.patch("/api/admin/users/:userId/center-head", requireCenterHead, async (req: any, res) => {
    try {
      const { userId } = req.params;
      const { isCenterHead } = req.body;
      const currentUserId = req.user.claims?.sub || req.user.id;
      
      // Prevent users from removing their own center head status
      if (userId === currentUserId && !isCenterHead) {
        return res.status(400).json({ message: "Cannot remove your own center head status" });
      }
      
      // Update user's center head status (need to add this method to storage)
      await storage.updateUser(userId, { isCenterHead });
      
      res.json({ message: "Center head status updated successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to update center head status" });
    }
  });
  
  // Delete Department
  app.delete("/api/departments/:id", requireCenterHead, async (req, res) => {
    try {
      const departmentId = parseInt(req.params.id);
      
      // Check if department has any doctors, clinics, or other data
      const departmentData = await storage.getDepartmentData(departmentId);
      
      if (departmentData.doctors.length > 0) {
        return res.status(400).json({ 
          message: "Cannot delete department with existing doctors. Please remove or transfer all doctors first." 
        });
      }
      
      if (departmentData.clinics.length > 0) {
        return res.status(400).json({ 
          message: "Cannot delete department with existing clinics. Please remove all clinics first." 
        });
      }
      
      // Delete department and all related data
      await storage.deleteDepartment(departmentId);
      
      res.json({ message: "Department deleted successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to delete department" });
    }
  });
  
  // Delete user route
  app.delete("/api/admin/users/:userId", requireCenterHead, async (req: any, res) => {
    try {
      const { userId } = req.params;
      const currentUserId = req.user.claims?.sub || req.user.id;
      
      // Prevent self-deletion
      if (userId === currentUserId) {
        return res.status(400).json({ message: "Cannot delete your own account" });
      }
      
      await storage.deleteUser(userId);
      res.json({ message: "User deleted successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to delete user" });
    }
  });
  
  // Change user password route (admin only)
  app.patch("/api/admin/users/:userId/password", requireCenterHead, async (req: any, res) => {
    try {
      const { userId } = req.params;
      const { newPassword } = req.body;
      
      if (!newPassword || newPassword.length < 6) {
        return res.status(400).json({ message: "Password must be at least 6 characters long" });
      }
      
      const user = await storage.getUser(userId);
      if (!user) {
        return res.status(404).json({ message: "User not found" });
      }
      
      // Hash the new password
      const { hashPassword } = await import("../localAuth");
      const passwordHash = await hashPassword(newPassword);
      
      // Update user password
      await storage.updateUserPassword(userId, passwordHash);
      
      res.json({ message: "Password updated successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to update password" });
    }
  });
  
  // Update user information route (admin only)
  app.patch("/api/admin/users/:userId", requireCenterHead, async (req: any, res) => {
    try {
      const { userId } = req.params;
      const { firstName, lastName, email, username, isCenterHead } = req.body;
      
      const user = await storage.getUser(userId);
      if (!user) {
        return res.status(404).json({ message: "User not found" });
      }
      
      // Update user information
      await storage.updateUser(userId, {
        firstName,
        lastName,
        email,
        username,
        isCenterHead
      });
      
      res.json({ message: "User updated successfully" });
    } catch (error) {
      res.status(500).json({ message: "Failed to update user" });
    }
  });
  
}
