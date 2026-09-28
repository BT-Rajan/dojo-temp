import type { Express } from "express";
import { storage } from "../storage";
import { insertOvertimeSessionSchema, insertOvertimeSlotEntrySchema, insertOvertimeProcedureLogSchema, insertOvertimeSlotProcedureLogSchema } from "@shared/schema";
import { z } from "zod";

export function registerOvertimeRoutes(app: Express): void {
  // ─── Overtime Portal Routes ──────────────────────────────────────────────
  
  // List overtime sessions by department + optional date or date range
  app.get('/api/overtime/sessions', async (req, res) => {
    try {
      const departmentId = parseInt(req.query.departmentId as string);
      if (!departmentId) return res.status(400).json({ message: "departmentId required" });
      const { date, startDate, endDate } = req.query as Record<string, string>;
      let sessions;
      if (startDate && endDate) {
        sessions = await storage.getOvertimeSessionsByDateRange(departmentId, startDate, endDate);
      } else {
        sessions = await storage.getOvertimeSessions(departmentId, date);
      }
      res.set("Cache-Control", "no-store");
      res.json(sessions);
    } catch (error) {
      console.error("Error fetching overtime sessions:", error);
      res.status(500).json({ message: "Failed to fetch overtime sessions" });
    }
  });
  
  // Create a new overtime session
  app.post('/api/overtime/sessions', async (req, res) => {
    try {
      console.log("[Overtime] Creating session:", JSON.stringify(req.body));
      const data = insertOvertimeSessionSchema.parse(req.body);
      const session = await storage.createOvertimeSession(data);
      console.log("[Overtime] Session created:", session.id);
      res.json(session);
    } catch (error) {
      console.error("[Overtime] Error creating session:", error);
      res.status(500).json({ message: "Failed to create overtime session" });
    }
  });
  
  // Update overtime session (open/close, change doctor, notes)
  app.patch('/api/overtime/sessions/:id', async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertOvertimeSessionSchema.partial().parse(req.body);
      const session = await storage.updateOvertimeSession(id, data);
      res.json(session);
    } catch (error) {
      console.error("Error updating overtime session:", error);
      res.status(500).json({ message: "Failed to update overtime session" });
    }
  });
  
  // Delete overtime session (also cascades to slot entries)
  app.delete('/api/overtime/sessions/:id', async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteOvertimeSession(id);
      res.json({ success: true });
    } catch (error) {
      console.error("Error deleting overtime session:", error);
      res.status(500).json({ message: "Failed to delete overtime session" });
    }
  });
  
  // List slot entries for a session
  app.get('/api/overtime/slots', async (req, res) => {
    try {
      const sessionId = parseInt(req.query.sessionId as string);
      if (!sessionId) return res.status(400).json({ message: "sessionId required" });
      const entries = await storage.getOvertimeSlotEntries(sessionId);
      res.set("Cache-Control", "no-store");
      res.json(entries);
    } catch (error) {
      console.error("Error fetching overtime slots:", error);
      res.status(500).json({ message: "Failed to fetch overtime slots" });
    }
  });
  
  // Create a slot entry
  app.post('/api/overtime/slots', async (req, res) => {
    try {
      const data = insertOvertimeSlotEntrySchema.parse(req.body);
      const entry = await storage.createOvertimeSlotEntry(data);
      res.json(entry);
    } catch (error) {
      console.error("Error creating overtime slot:", error);
      res.status(500).json({ message: "Failed to create overtime slot" });
    }
  });
  
  // Update a slot entry
  app.put('/api/overtime/slots/:id', async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertOvertimeSlotEntrySchema.partial().parse(req.body);
      const entry = await storage.updateOvertimeSlotEntry(id, data);
      res.json(entry);
    } catch (error) {
      console.error("Error updating overtime slot:", error);
      res.status(500).json({ message: "Failed to update overtime slot" });
    }
  });
  
  // Delete a slot entry
  app.delete('/api/overtime/slots/:id', async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteOvertimeSlotEntry(id);
      res.json({ success: true });
    } catch (error) {
      console.error("Error deleting overtime slot:", error);
      res.status(500).json({ message: "Failed to delete overtime slot" });
    }
  });
  
  // Get overtime procedure log for a session
  app.get('/api/overtime/procedure-logs', async (req, res) => {
    try {
      const sessionId = parseInt(req.query.sessionId as string);
      if (!sessionId) return res.status(400).json({ message: "sessionId required" });
      const log = await storage.getOvertimeProcedureLogBySession(sessionId);
      res.json(log || null);
    } catch (error) {
      console.error("Error fetching overtime procedure log:", error);
      res.status(500).json({ message: "Failed to fetch overtime procedure log" });
    }
  });
  
  // Create or update (upsert) overtime procedure log
  app.post('/api/overtime/procedure-logs', async (req, res) => {
    try {
      const data = insertOvertimeProcedureLogSchema.parse(req.body);
      const log = await storage.upsertOvertimeProcedureLog(data);
      res.json(log);
    } catch (error) {
      console.error("Error saving overtime procedure log:", error);
      res.status(500).json({ message: "Failed to save overtime procedure log" });
    }
  });
  
  // Get aggregated overtime stats for a department
  app.get('/api/overtime/stats', async (req, res) => {
    try {
      const departmentId = parseInt(req.query.departmentId as string);
      const startDate = req.query.startDate as string;
      const endDate = req.query.endDate as string;
      const doctorId = req.query.doctorId ? parseInt(req.query.doctorId as string) : undefined;
      if (!departmentId || !startDate || !endDate) {
        return res.status(400).json({ message: "departmentId, startDate, and endDate are required" });
      }
      const stats = await storage.getAggregatedOvertimeProcedureStats(departmentId, startDate, endDate, doctorId);
      res.set("Cache-Control", "no-store");
      res.json(stats);
    } catch (error) {
      console.error("Error fetching overtime stats:", error);
      res.status(500).json({ message: "Failed to fetch overtime stats" });
    }
  });
  
  // Get slot procedure logs for a session (per-patient)
  app.get('/api/overtime/slot-logs', async (req, res) => {
    try {
      const sessionId = parseInt(req.query.sessionId as string);
      if (!sessionId) return res.status(400).json({ message: "sessionId required" });
      const logs = await storage.getOvertimeSlotProcedureLogsBySession(sessionId);
      res.set("Cache-Control", "no-store");
      res.json(logs);
    } catch (error) {
      console.error("Error fetching slot procedure logs:", error);
      res.status(500).json({ message: "Failed to fetch slot procedure logs" });
    }
  });
  
  // Create or update a per-patient slot procedure log
  app.post('/api/overtime/slot-logs', async (req, res) => {
    try {
      const data = insertOvertimeSlotProcedureLogSchema.parse(req.body);
      const log = await storage.upsertOvertimeSlotProcedureLog(data);
      res.json(log);
    } catch (error) {
      console.error("Error saving slot procedure log:", error);
      res.status(500).json({ message: "Failed to save slot procedure log" });
    }
  });
  
  // Copy this week's sessions to next week
  app.post('/api/overtime/copy-week', async (req, res) => {
    try {
      const { departmentId, fromStart, fromEnd } = req.body;
      if (!departmentId || !fromStart || !fromEnd) {
        return res.status(400).json({ message: "departmentId, fromStart, fromEnd required" });
      }
      const result = await storage.copyWeekOvertimeSessions(parseInt(departmentId), fromStart, fromEnd);
      res.json(result);
    } catch (error) {
      console.error("Error copying week sessions:", error);
      res.status(500).json({ message: "Failed to copy sessions" });
    }
  });
  
  // ── Doctor portal — no main auth required ────────────────────────────────
  
  // Clinic day view filtered to one doctor (for doctor portal)
  app.get('/api/doctor/:doctorId/clinic-day', async (req, res) => {
    try {
      const doctorId = parseInt(req.params.doctorId);
      const date = req.query.date as string;
      if (!date) return res.status(400).json({ message: "date required" });
  
      const doctor = await storage.getDoctor(doctorId);
      if (!doctor) return res.status(404).json({ message: "Doctor not found" });
      const departmentId = doctor.departmentId;
  
      const weekday = new Date(date + 'T12:00:00').getDay();
      const assignments = await storage.getClinicAssignmentsByWeekdayAndDepartment(weekday, departmentId);
      const appointments = await storage.getAppointmentsByDepartmentAndDate(departmentId, date);
      const activeLeaves = await storage.getActiveLeavesByDepartment(departmentId);
      const doctorsOnLeave = new Set(activeLeaves
        .filter((l: any) => l.startDate <= date && l.endDate >= date)
        .map((l: any) => l.doctorId));
  
      // Build appointment index by clinicId (same logic as /api/department/:id/clinic-day)
      const apptsByClinic: Record<number, any[]> = {};
      for (const appt of appointments) {
        const cid = (appt as any).clinicId;
        if (cid) {
          if (!apptsByClinic[cid]) apptsByClinic[cid] = [];
          apptsByClinic[cid].push(appt);
        } else {
          const did = (appt as any).doctorId;
          if (did) {
            const assign = assignments.find((a: any) => a.doctorId === did);
            if (assign) {
              if (!apptsByClinic[assign.clinicId]) apptsByClinic[assign.clinicId] = [];
              apptsByClinic[assign.clinicId].push({ ...appt, clinicId: assign.clinicId });
            }
          }
        }
      }
  
      // Filter assignments to only this doctor
      const doctorAssignments = assignments.filter((a: any) => a.doctorId === doctorId);
  
      const entries = doctorAssignments.map((a: any) => {
        const doc = (a as any).doctor || { id: a.doctorId, name: '', title: '' };
        const clinic = (a as any).clinic || { id: a.clinicId, name: '', startTime: '08:00', endTime: '14:00' };
        const clinicAppts = apptsByClinic[a.clinicId] || [];
        return {
          assignmentId: a.id,
          clinic: { id: clinic.id, name: clinic.name, startTime: clinic.startTime, endTime: clinic.endTime },
          doctor: { id: doc.id, name: doc.name, title: doc.title },
          isOnLeave: doctorsOnLeave.has(a.doctorId),
          appointments: clinicAppts.map((ap: any) => ({
            id: ap.id, startTime: ap.startTime, endTime: ap.endTime, status: ap.status,
            appointmentDate: date,
            reasonForVisit: ap.reasonForVisit,
            patient: ap.patient || { firstName: (ap.patientName || '').split(' ')[0], lastName: (ap.patientName || '').split(' ').slice(1).join(' '), phone: ap.patientPhone || '' },
          })),
        };
      });
  
      res.set('Cache-Control', 'no-store');
      res.json(entries);
    } catch (e) {
      console.error("Doctor clinic-day error:", e);
      res.status(500).json({ message: "Failed to load clinic schedule" });
    }
  });
  
  // Procedure stats for one doctor (for doctor portal)
  app.get('/api/doctor/:doctorId/my-stats', async (req, res) => {
    try {
      const doctorId = parseInt(req.params.doctorId);
      const { startDate, endDate } = req.query;
      if (!startDate || !endDate) return res.status(400).json({ message: "startDate and endDate required" });
  
      const doctor = await storage.getDoctor(doctorId);
      if (!doctor) return res.status(404).json({ message: "Doctor not found" });
  
      const stats = await storage.getAggregatedProcedureStats(
        doctor.departmentId,
        startDate as string,
        endDate as string,
        doctorId
      );
      res.json(stats);
    } catch (e) {
      console.error("Doctor my-stats error:", e);
      res.status(500).json({ message: "Failed to load stats" });
    }
  });
  
  // ── Call Center & Exam Schedule ────────────────────────────────────────────
  
  // Public: list departments with their names (for call center login selector)
}
