import type { Express } from "express";
import { storage } from "../storage";
import { insertProcedureLogSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerProceduresRoutes(app: Express): void {
  // Procedure logging routes
  app.get("/api/procedure-logs", isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId, doctorId, startDate, endDate } = req.query;

      if (departmentId && startDate && endDate) {
        const logs = await storage.getProcedureLogsByDateRange(startDate as string, endDate as string);
        const filteredLogs = logs.filter(log => log.departmentId === parseInt(departmentId as string));
        res.json(filteredLogs);
      } else if (departmentId) {
        const logs = await storage.getProcedureLogsByDepartment(parseInt(departmentId as string));
        res.json(logs);
      } else if (doctorId && startDate && endDate) {
        const logs = await storage.getProcedureLogsByDoctorAndDateRange(
          parseInt(doctorId as string),
          startDate as string,
          endDate as string
        );
        res.json(logs);
      } else if (doctorId) {
        const logs = await storage.getProcedureLogsByDoctor(parseInt(doctorId as string));
        res.json(logs);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const logs = await storage.getProcedureLogs();
          res.json(logs);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch procedure logs" });
    }
  });
  
  app.post("/api/procedure-logs", isAuthenticated, async (req, res) => {
    try {
      const procedureLogData = insertProcedureLogSchema.parse(req.body);
      const procedureLog = await storage.createProcedureLog(procedureLogData);
      res.status(201).json(procedureLog);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid procedure log data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create procedure log" });
    }
  });
  
  app.get("/api/procedure-stats/doctor/:doctorId", isAuthenticated, async (req, res) => {
    try {
      const doctorId = parseInt(req.params.doctorId);
      const { year, month } = req.query;
      
      const stats = await storage.getProcedureStatsByDoctor(
        doctorId,
        year ? parseInt(year as string) : undefined,
        month ? parseInt(month as string) : undefined
      );
      res.json(stats);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch procedure stats for doctor" });
    }
  });
  
  app.get("/api/procedure-stats/department/:departmentId", isAuthenticated, async (req, res) => {
    try {
      const departmentId = parseInt(req.params.departmentId);
      const { year, month } = req.query;
      
      const stats = await storage.getProcedureStatsByDepartment(
        departmentId,
        year ? parseInt(year as string) : undefined,
        month ? parseInt(month as string) : undefined
      );
      res.json(stats);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch procedure stats for department" });
    }
  });
  
  // Monthly procedure report endpoint
  app.get("/api/monthly-procedure-report", isAuthenticated, async (req, res) => {
    try {
      const { departmentId, year, month, doctorId } = req.query;
      
      if (!year || !month) {
        return res.status(400).json({ message: "Year and month are required" });
      }
      
      const yearNum = parseInt(year as string);
      const monthNum = parseInt(month as string);
      
      if (doctorId) {
        // Single doctor report
        const doctor = await storage.getDoctor(parseInt(doctorId as string));
        if (!doctor) {
          return res.status(404).json({ message: "Doctor not found" });
        }
        
        const stats = await storage.getProcedureStatsByDoctor(doctor.id, yearNum, monthNum);
        
        const report = {
          reportType: "doctor",
          period: { year: yearNum, month: monthNum },
          doctor: doctor,
          department: doctor.departmentId ? await storage.getDepartment(doctor.departmentId) : null,
          summary: {
            totalPatientsTreated: stats.totalAppointments,
            totalProceduresCompleted: Object.values(stats.procedureTotals).reduce((sum, count) => sum + count, 0),
            appointmentsCompleted: stats.completedAppointments,
          },
          procedures: stats.procedureTotals,
          generatedAt: new Date().toISOString(),
        };
        
        res.json(report);
      } else if (departmentId) {
        // Department report
        const department = await storage.getDepartment(parseInt(departmentId as string));
        if (!department) {
          return res.status(404).json({ message: "Department not found" });
        }
        
        const departmentStats = await storage.getProcedureStatsByDepartment(
          parseInt(departmentId as string), 
          yearNum, 
          monthNum
        );
        
        // Aggregate totals for department
        const departmentTotals = {
          totalPatientsTreated: 0,
          totalProceduresCompleted: 0,
          appointmentsCompleted: 0,
          procedures: {} as Record<string, number>,
        };
        
        const doctorReports = departmentStats.map(doctorStat => {
          departmentTotals.totalPatientsTreated += doctorStat.totalAppointments;
          departmentTotals.appointmentsCompleted += doctorStat.completedAppointments;
          
          // Aggregate procedure totals
          Object.entries(doctorStat.procedureTotals).forEach(([procedure, count]) => {
            departmentTotals.procedures[procedure] = (departmentTotals.procedures[procedure] || 0) + count;
            departmentTotals.totalProceduresCompleted += count;
          });
          
          return {
            doctor: doctorStat.doctor,
            summary: {
              totalPatientsTreated: doctorStat.totalAppointments,
              totalProceduresCompleted: Object.values(doctorStat.procedureTotals).reduce((sum, count) => sum + count, 0),
              appointmentsCompleted: doctorStat.completedAppointments,
            },
            procedures: doctorStat.procedureTotals,
          };
        });
        
        const report = {
          reportType: "department",
          period: { year: yearNum, month: monthNum },
          department: department,
          summary: departmentTotals,
          doctorReports: doctorReports,
          generatedAt: new Date().toISOString(),
        };
        
        res.json(report);
      } else {
        return res.status(400).json({ message: "Either departmentId or doctorId is required" });
      }
    } catch (error) {
      console.error("Monthly report error:", error);
      res.status(500).json({ message: "Failed to generate monthly procedure report" });
    }
  });
  
}
