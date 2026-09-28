import bcrypt from "bcryptjs";
import passport from "passport";
import { Strategy as LocalStrategy } from "passport-local";
import type { Express, RequestHandler } from "express";
import { storage } from "./storage";

export function setupLocalAuth(app: Express) {
  // Local strategy for username/password login
  passport.use(new LocalStrategy(
    {
      usernameField: 'username',
      passwordField: 'password'
    },
    async (username, password, done) => {
      try {
        const user = await storage.getUserByUsername(username);
        
        if (!user || !user.isLocalAccount || !user.passwordHash) {
          return done(null, false, { message: 'Invalid credentials' });
        }

        const isValid = await bcrypt.compare(password, user.passwordHash);
        if (!isValid) {
          return done(null, false, { message: 'Invalid credentials' });
        }
        return done(null, user);
      } catch (error) {
        return done(error);
      }
    }
  ));

  // Local login route
  app.post("/api/login/local", (req, res, next) => {
    passport.authenticate('local', (err: any, user: any, info: any) => {
      if (err) {
        console.error('Auth error:', err);
        return next(err);
      }
      
      if (!user) {
        console.log('Auth failed:', info);
        return res.redirect('/login?error=invalid');
      }

      req.logIn(user, (err: any) => {
        if (err) {
          console.error('Login error:', err);
          return next(err);
        }
        
        console.log('Auth successful for user:', user.username);
        
        // Check for redirect parameter, default to home page
        const redirectTo = req.body.redirect || '/';
        return res.redirect(redirectTo);
      });
    })(req, res, next);
  });

  // Local logout route
  app.post("/api/logout/local", (req, res) => {
    req.logout((err) => {
      if (err) {
        return res.status(500).json({ message: "Failed to logout" });
      }
      res.json({ message: "Logged out successfully" });
    });
  });
}

export async function hashPassword(password: string): Promise<string> {
  return await bcrypt.hash(password, 12);
}

export const requireCenterHead: RequestHandler = async (req: any, res, next) => {
  if (!req.isAuthenticated()) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = req.user.claims?.sub || req.user.id;
  const user = await storage.getUser(userId);
  
  if (!user?.isCenterHead) {
    return res.status(403).json({ message: "Requires center head privileges" });
  }

  next();
};

// Middleware to check emergency assignment permissions
export const requireEmergencyAccess: (departmentId: number) => RequestHandler = 
  (departmentId: number) => 
  async (req: any, res, next) => {
    if (!req.isAuthenticated()) {
      return res.status(401).json({ message: "Unauthorized" });
    }

    const userId = req.user.claims?.sub || req.user.id;
    const user = await storage.getUser(userId);
    
    // Center heads have access to everything
    if (user?.isCenterHead) {
      return next();
    }

    // Check department membership and emergency permissions
    const members = await storage.getDepartmentMembers(departmentId);
    const userMembership = members.find(m => m.userId === userId);
    
    if (!userMembership) {
      return res.status(403).json({ message: "No access to this department" });
    }

    // Check if user has emergency assignment permissions or is a department head
    if (!userMembership.canAssignEmergencies && userMembership.role !== "head") {
      return res.status(403).json({ message: "No emergency assignment permissions" });
    }

    next();
  };

// Middleware to check leave management permissions  
export const requireLeaveAccess: (departmentId: number) => RequestHandler = 
  (departmentId: number) => 
  async (req: any, res, next) => {
    if (!req.isAuthenticated()) {
      return res.status(401).json({ message: "Unauthorized" });
    }

    const userId = req.user.claims?.sub || req.user.id;
    const user = await storage.getUser(userId);
    
    // Center heads have access to everything
    if (user?.isCenterHead) {
      return next();
    }

    // Check department membership and leave management permissions
    const members = await storage.getDepartmentMembers(departmentId);
    const userMembership = members.find(m => m.userId === userId);
    
    if (!userMembership) {
      return res.status(403).json({ message: "No access to this department" });
    }

    // Check if user has leave management permissions or is a department head
    if (!userMembership.canManageLeaves && userMembership.role !== "head") {
      return res.status(403).json({ message: "No leave management permissions" });
    }

    next();
  };

export const requireDepartmentAccess: (departmentId: number, allowViewOnly?: boolean) => RequestHandler = 
  (departmentId: number, allowViewOnly: boolean = false) => 
  async (req: any, res, next) => {
    if (!req.isAuthenticated()) {
      return res.status(401).json({ message: "Unauthorized" });
    }

    const userId = req.user.claims?.sub || req.user.id;
    const user = await storage.getUser(userId);
    
    // Center heads have access to everything
    if (user?.isCenterHead) {
      return next();
    }

    // Check department membership
    const userDepartments = await storage.getUserDepartments(userId);
    const membershipInDept = userDepartments.find(dept => dept.id === departmentId);
    
    if (!membershipInDept) {
      return res.status(403).json({ message: "No access to this department" });
    }

    // Check if user has edit permissions (unless view-only is allowed)
    if (!allowViewOnly) {
      const members = await storage.getDepartmentMembers(departmentId);
      const userMembership = members.find(m => m.userId === userId);
      
      if (!userMembership?.canEdit) {
        return res.status(403).json({ message: "No edit permissions for this department" });
      }
    }

    next();
  };