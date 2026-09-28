import type { Express } from "express";
import { storage } from "../storage";
import { insertAppointmentSlotSchema, insertAppointmentSchema } from "@shared/schema";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";
import { sendNotificationToDoctor } from "./notify";

export function registerAppointmentsRoutes(app: Express): void {
  app.post('/api/appointments', async (req, res) => {
    try {
      const { doctorId, patientName, patientPhone, procedure, appointmentDate, startTime, endTime, appointmentTime, notes, status, type, clinicId } = req.body;
      
      console.log('Appointment creation request:', { doctorId, patientName, patientPhone, procedure, appointmentDate, startTime, endTime, appointmentTime, notes, status, type });
      
      // Use startTime/endTime if provided, otherwise fallback to appointmentTime
      const appointmentStartTime = startTime || appointmentTime;
      const appointmentEndTime = endTime || appointmentTime;
      
      if (!doctorId || !patientName || !patientPhone || !procedure || !appointmentDate || !appointmentStartTime) {
        return res.status(400).json({ message: 'Missing required fields' });
      }
  
      // Create or find patient first
      const patient = await storage.createPatient({
        firstName: patientName.split(' ')[0] || patientName,
        lastName: patientName.split(' ').slice(1).join(' ') || '',
        phone: patientPhone,
        email: '',
        dateOfBirth: null,
        address: null,
        emergencyContact: null,
        medicalHistory: null
      });
  
      // Create a simple appointment slot first, then appointment
      const appointmentSlot = await storage.createAppointmentSlot({
        doctorId: parseInt(doctorId),
        date: appointmentDate,
        startTime: appointmentStartTime,
        endTime: appointmentEndTime,
        duration: 30,
        isAvailable: true
      });
  
      // Create appointment
      const appointment = await storage.createAppointment({
        doctorId: parseInt(doctorId),
        patientId: patient.id,
        slotId: appointmentSlot.id,
        appointmentDate,
        startTime: appointmentStartTime,
        endTime: appointmentEndTime,
        status: status || 'scheduled',
        type: type || 'consultation',
        reasonForVisit: procedure,
        notes: notes || null,
        clinicId: clinicId ? parseInt(clinicId) : null
      });
      
      console.log('Appointment created successfully:', appointment.id);
  
      // Notify the doctor via WebSocket that a new patient has been added to their schedule
      const newApptNotification = {
        type: 'appointment_added',
        appointmentId: appointment.id,
        patientName,
        appointmentTime: appointmentStartTime,
        appointmentDate,
        message: `New patient scheduled: ${patientName} at ${appointmentStartTime}`
      };
      sendNotificationToDoctor(parseInt(doctorId), newApptNotification);
      
      // Return appointment with patient info for immediate display
      const fullAppointment = {
        ...appointment,
        patient,
        patientName,
        patientPhone,
        procedure
      };
  
      res.status(201).json(fullAppointment);
    } catch (error) {
      console.error('Error creating appointment:', error);
      res.status(500).json({ message: 'Failed to create appointment' });
    }
  });
  
  // Get doctor's appointments
  app.get('/api/appointments', async (req, res) => {
    try {
      const { doctorId, date } = req.query;
      
      console.log('Appointments API called with:', { doctorId, date });
      
      if (!doctorId) {
        return res.status(400).json({ message: 'Doctor ID is required' });
      }
  
      let appointments;
      if (date && storage.getAppointmentsByDoctorAndDate) {
        appointments = await storage.getAppointmentsByDoctorAndDate(parseInt(doctorId as string), date as string);
      } else {
        appointments = await storage.getAppointmentsByDoctor(parseInt(doctorId as string));
      }
      
      console.log('Returning appointments:', appointments.length);
      res.json(appointments);
    } catch (error) {
      console.error('Error fetching appointments:', error);
      res.status(500).json({ message: 'Failed to fetch appointments' });
    }
  });
  
  // Update appointment
  app.put('/api/appointments/:id', async (req, res) => {
    try {
      const appointmentId = parseInt(req.params.id);
      const { doctorId, patientName, patientPhone, procedure, appointmentDate, startTime, endTime, appointmentTime, notes, status, type } = req.body;
      
      console.log('Appointment update request:', { appointmentId, doctorId, patientName, patientPhone, procedure, appointmentDate, startTime, endTime, notes });
      
      // Use startTime/endTime if provided, otherwise fallback to appointmentTime
      const appointmentStartTime = startTime || appointmentTime;
      const appointmentEndTime = endTime || appointmentTime;
      
      if (!appointmentId || !doctorId || !patientName || !appointmentDate || !appointmentStartTime) {
        return res.status(400).json({ message: 'Missing required fields' });
      }
  
      // Update appointment
      const updatedAppointment = await storage.updateAppointment(appointmentId, {
        doctorId: parseInt(doctorId),
        appointmentDate,
        startTime: appointmentStartTime,
        endTime: appointmentEndTime,
        status: status || 'scheduled',
        type: type || 'consultation',
        reasonForVisit: procedure,
        notes: notes || null,
      });
  
      // Get the appointment to find patient ID, then update patient info
      const appointment = await storage.getAppointmentById(appointmentId);
      if (appointment && appointment.patientId) {
        await storage.updatePatient(appointment.patientId, {
          firstName: patientName.split(' ')[0] || patientName,
          lastName: patientName.split(' ').slice(1).join(' ') || '',
          phone: patientPhone,
        });
      }
      
      console.log('Appointment updated successfully:', appointmentId);
      res.json(updatedAppointment);
    } catch (error) {
      console.error('Error updating appointment:', error);
      res.status(500).json({ message: 'Failed to update appointment' });
    }
  });
  
  // Delete appointment
  app.delete('/api/appointments/:id', async (req, res) => {
    try {
      const appointmentId = parseInt(req.params.id);
      
      console.log('Appointment delete request:', appointmentId);
      
      if (!appointmentId) {
        return res.status(400).json({ message: 'Invalid appointment ID' });
      }
  
      await storage.deleteAppointment(appointmentId);
      
      console.log('Appointment deleted successfully:', appointmentId);
      res.json({ message: 'Appointment deleted successfully' });
    } catch (error) {
      console.error('Error deleting appointment:', error);
      res.status(500).json({ message: 'Failed to delete appointment' });
    }
  });
  
  // Update appointment status
  app.patch('/api/appointments/:id/status', async (req, res) => {
    try {
      const appointmentId = parseInt(req.params.id);
      const { status } = req.body;
      
      console.log('Appointment status update request:', { appointmentId, status });
      
      if (!appointmentId) {
        return res.status(400).json({ message: 'Invalid appointment ID' });
      }
  
      if (!status || !['scheduled', 'confirmed', 'arrived', 'completed', 'cancelled', 'missed'].includes(status)) {
        return res.status(400).json({ message: 'Invalid status' });
      }
  
      const updatedAppointment = await storage.updateAppointmentStatus(appointmentId, status);
      
      // Send notification to doctor if patient has arrived
      if (status === 'arrived' && updatedAppointment) {
        // Get the appointment details to find the doctor and patient
        const appointment = await storage.getAppointmentById(appointmentId);
        if (appointment && appointment.doctorId) {
          // Get patient information
          const patient = await storage.getPatient(appointment.patientId);
          const patientName = patient ? `${patient.firstName} ${patient.lastName}` : 'Patient';
          
          const notification = {
            type: 'patient_arrived',
            appointmentId: appointmentId,
            patientName: patientName,
            appointmentTime: appointment.startTime,
            appointmentDate: appointment.appointmentDate,
            message: `Patient ${patientName} has arrived for their ${appointment.startTime} appointment`
          };
          
          const notificationSent = sendNotificationToDoctor(appointment.doctorId, notification);
          console.log(`Notification ${notificationSent ? 'sent' : 'failed'} to doctor ${appointment.doctorId} for patient arrival`);
        }
      }
      
      console.log('Appointment status updated successfully:', { appointmentId, status });
      res.json(updatedAppointment);
    } catch (error) {
      console.error('Error updating appointment status:', error);
      res.status(500).json({ message: 'Failed to update appointment status' });
    }
  });
  
  // Department head monitoring routes for appointments
  app.get('/api/department/:departmentId/appointments', async (req: any, res) => {
    try {
      // Check authentication
      if (!req.isAuthenticated()) {
        return res.status(401).json({ message: "Unauthorized" });
      }
  
      const departmentId = parseInt(req.params.departmentId);
      const { date, doctorId, startDate, endDate } = req.query;
      const userId = req.user.claims?.sub || req.user.id;
      
      // Check department access
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        const userDepartments = await storage.getUserDepartments(userId);
        const hasAccess = userDepartments.some(dept => dept.id === departmentId);
        
        if (!hasAccess) {
          return res.status(403).json({ message: "No access to this department" });
        }
      }
      
      console.log('Department appointments requested:', { departmentId, date, doctorId, startDate, endDate });
      
      let appointments;
      
      if (doctorId) {
        // Get appointments for specific doctor in department
        if (date) {
          appointments = await storage.getAppointmentsByDoctorAndDate(parseInt(doctorId as string), date as string);
        } else if (startDate && endDate) {
          appointments = await storage.getAppointmentsByDoctorAndDateRange(parseInt(doctorId as string), startDate as string, endDate as string);
        } else {
          appointments = await storage.getAppointmentsByDoctor(parseInt(doctorId as string));
        }
      } else {
        // Get all appointments for department
        if (date) {
          appointments = await storage.getAppointmentsByDepartmentAndDate(departmentId, date as string);
        } else if (startDate && endDate) {
          appointments = await storage.getAppointmentsByDepartmentAndDateRange(departmentId, startDate as string, endDate as string);
        } else {
          appointments = await storage.getAppointmentsByDepartment(departmentId);
        }
      }
      
      res.json(appointments);
    } catch (error) {
      console.error('Error fetching department appointments:', error);
      res.status(500).json({ message: 'Failed to fetch department appointments' });
    }
  });
  
  // Clinic Day View — all clinics open on a given date with assigned doctors + appointments
  app.get('/api/department/:departmentId/clinic-day', async (req: any, res) => {
    try {
      if (!req.isAuthenticated()) return res.status(401).json({ message: "Unauthorized" });
      const departmentId = parseInt(req.params.departmentId);
      const date = req.query.date as string;
      if (!date) return res.status(400).json({ message: "date query param required (YYYY-MM-DD)" });
  
      const userId = req.user.claims?.sub || req.user.id;
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        const userDepts = await storage.getUserDepartments(userId);
        if (!userDepts.some(d => d.id === departmentId))
          return res.status(403).json({ message: "No access to this department" });
      }
  
      const weekday = new Date(date + 'T12:00:00').getDay();
      const assignments = await storage.getClinicAssignmentsByWeekdayAndDepartment(weekday, departmentId);
      const appointments = await storage.getAppointmentsByDepartmentAndDate(departmentId, date);
      const activeLeaves = await storage.getActiveLeavesByDepartment(departmentId);
      const doctorsOnLeave = new Set(activeLeaves
        .filter(l => l.startDate <= date && l.endDate >= date)
        .map(l => l.doctorId));
  
      const apptsByClinic: Record<number, any[]> = {};
      for (const appt of appointments) {
        const cid = (appt as any).clinicId;
        if (cid) {
          if (!apptsByClinic[cid]) apptsByClinic[cid] = [];
          apptsByClinic[cid].push(appt);
        }
        // Also index by doctor if no clinicId
        const did = (appt as any).doctorId;
        if (!cid && did) {
          const assign = assignments.find(a => a.doctorId === did);
          if (assign) {
            const clinicId = assign.clinicId;
            if (!apptsByClinic[clinicId]) apptsByClinic[clinicId] = [];
            apptsByClinic[clinicId].push({ ...appt, clinicId });
          }
        }
      }
  
      const result = assignments.map(a => ({
        assignmentId: a.id,
        clinic: a.clinic,
        doctor: a.doctor,
        isOnLeave: doctorsOnLeave.has(a.doctorId),
        appointments: (apptsByClinic[a.clinicId] || []).sort((x: any, y: any) => (x.startTime || '').localeCompare(y.startTime || '')),
      }));
  
      res.set('Cache-Control', 'no-store');
      res.json(result);
    } catch (error) {
      console.error('Error fetching clinic day view:', error);
      res.status(500).json({ message: 'Failed to fetch clinic day view' });
    }
  });
  
  // Get department appointment statistics
  app.get('/api/department/:departmentId/appointments/stats', async (req: any, res) => {
    try {
      // Check authentication
      if (!req.isAuthenticated()) {
        return res.status(401).json({ message: "Unauthorized" });
      }
  
      const departmentId = parseInt(req.params.departmentId);
      const { startDate, endDate } = req.query;
      const userId = req.user.claims?.sub || req.user.id;
      
      // Check department access
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        const userDepartments = await storage.getUserDepartments(userId);
        const hasAccess = userDepartments.some(dept => dept.id === departmentId);
        
        if (!hasAccess) {
          return res.status(403).json({ message: "No access to this department" });
        }
      }
      
      const stats = await storage.getDepartmentAppointmentStats(
        departmentId, 
        startDate as string, 
        endDate as string
      );
      
      res.json(stats);
    } catch (error) {
      console.error('Error fetching department appointment stats:', error);
      res.status(500).json({ message: 'Failed to fetch department appointment statistics' });
    }
  });
  
  app.get('/api/department/:departmentId/procedure-stats', async (req: any, res) => {
    try {
      if (!req.isAuthenticated()) {
        return res.status(401).json({ message: "Unauthorized" });
      }
      const departmentId = parseInt(req.params.departmentId);
      const { startDate, endDate, doctorId } = req.query;
      const userId = req.user.claims?.sub || req.user.id;
  
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        const userDepartments = await storage.getUserDepartments(userId);
        const hasAccess = userDepartments.some(dept => dept.id === departmentId);
        if (!hasAccess) {
          return res.status(403).json({ message: "No access to this department" });
        }
      }
  
      if (!startDate || !endDate) {
        return res.status(400).json({ message: "startDate and endDate are required" });
      }
  
      const stats = await storage.getAggregatedProcedureStats(
        departmentId,
        startDate as string,
        endDate as string,
        doctorId ? parseInt(doctorId as string) : undefined
      );
      res.json(stats);
    } catch (error) {
      console.error('Error fetching procedure stats:', error);
      res.status(500).json({ message: 'Failed to fetch procedure statistics' });
    }
  });
  
  // Get doctor performance metrics for department head
  app.get('/api/department/:departmentId/doctors/performance', async (req: any, res) => {
    try {
      // Check authentication
      if (!req.isAuthenticated()) {
        return res.status(401).json({ message: "Unauthorized" });
      }
  
      const departmentId = parseInt(req.params.departmentId);
      const { startDate, endDate, doctorId } = req.query;
      const userId = req.user.claims?.sub || req.user.id;
      
      // Check department access
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        const userDepartments = await storage.getUserDepartments(userId);
        const hasAccess = userDepartments.some(dept => dept.id === departmentId);
        
        if (!hasAccess) {
          return res.status(403).json({ message: "No access to this department" });
        }
      }
      
      let performance = await storage.getDoctorPerformanceMetrics(
        departmentId, 
        startDate as string, 
        endDate as string
      );
      
      // Filter by specific doctor if doctorId is provided
      if (doctorId) {
        const selectedDoctorId = parseInt(doctorId as string);
        performance = performance.filter(metric => metric.doctor.id === selectedDoctorId);
      }
      
      res.json(performance);
    } catch (error) {
      console.error('Error fetching doctor performance metrics:', error);
      res.status(500).json({ message: 'Failed to fetch doctor performance metrics' });
    }
  });
  
  // NOTE: a duplicate, unreachable GET /api/permissions handler (shadowed by
  // the one in permissions.ts, which registers first) used to live here and
  // was removed — see permissions.ts for the real implementation.

  // Appointment slot routes
  app.get("/api/appointment-slots", isAuthenticated, async (req: any, res) => {
    try {
      const { doctorId, date } = req.query;
      if (doctorId && date) {
        const slots = await storage.getAppointmentSlotsByDoctorAndDate(parseInt(doctorId as string), date as string);
        res.json(slots);
      } else if (doctorId) {
        const slots = await storage.getAppointmentSlotsByDoctor(parseInt(doctorId as string));
        res.json(slots);
      } else if (date) {
        const slots = await storage.getAppointmentSlotsByDate(date as string);
        res.json(slots);
      } else {
        const userId = req.user?.claims?.sub || req.user?.id;
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const slots = await storage.getAppointmentSlots();
          res.json(slots);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch appointment slots" });
    }
  });
  
  app.post("/api/appointment-slots", isAuthenticated, async (req, res) => {
    try {
      const slotData = insertAppointmentSlotSchema.parse(req.body);
      const slot = await storage.createAppointmentSlot(slotData);
      res.status(201).json(slot);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid slot data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create appointment slot" });
    }
  });
  
  app.put("/api/appointment-slots/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const slotData = insertAppointmentSlotSchema.partial().parse(req.body);
      const slot = await storage.updateAppointmentSlot(id, slotData);
      res.json(slot);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid slot data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update appointment slot" });
    }
  });
  
  app.delete("/api/appointment-slots/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteAppointmentSlot(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete appointment slot" });
    }
  });
  
  // Appointment routes
  app.get("/api/appointments", isAuthenticated, async (req: any, res) => {
    try {
      const { doctorId, date, startDate, endDate } = req.query;
      const userId = req.user?.claims?.sub || req.user?.id;

      // Handle date range queries for weekly calendar
      if (startDate && endDate) {
        if (doctorId) {
          const appointments = await storage.getAppointmentsByDoctorAndDateRange(
            parseInt(doctorId as string),
            startDate as string,
            endDate as string
          );
          res.json(appointments);
        } else {
          const currentUser = await storage.getUser(userId);
          if (currentUser?.isCenterHead) {
            const appointments = await storage.getAppointmentsByDateRange(
              startDate as string,
              endDate as string
            );
            res.json(appointments);
          } else {
            res.json([]);
          }
        }
      } else if (doctorId && date) {
        const appointments = await storage.getAppointmentsByDoctorAndDate(parseInt(doctorId as string), date as string);
        res.json(appointments);
      } else if (doctorId) {
        const appointments = await storage.getAppointmentsByDoctor(parseInt(doctorId as string));
        res.json(appointments);
      } else if (date) {
        const appointments = await storage.getAppointmentsByDate(date as string);
        res.json(appointments);
      } else {
        const currentUser = await storage.getUser(userId);
        if (currentUser?.isCenterHead) {
          const appointments = await storage.getAppointments();
          res.json(appointments);
        } else {
          res.json([]);
        }
      }
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch appointments" });
    }
  });
  
  app.post("/api/appointments", isAuthenticated, async (req, res) => {
    try {
      const appointmentData = insertAppointmentSchema.parse(req.body);
      const appointment = await storage.createAppointment(appointmentData);
      res.status(201).json(appointment);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid appointment data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create appointment" });
    }
  });
  
  app.put("/api/appointments/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const appointmentData = insertAppointmentSchema.partial().parse(req.body);
      const appointment = await storage.updateAppointment(id, appointmentData);
      res.json(appointment);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid appointment data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to update appointment" });
    }
  });
  
  app.delete("/api/appointments/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteAppointment(id);
      res.status(204).send();
    } catch (error) {
      res.status(500).json({ message: "Failed to delete appointment" });
    }
  });
  
}
