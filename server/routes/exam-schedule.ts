import type { Express } from "express";
import { storage } from "../storage";
import { z } from "zod";
import { isAuthenticated } from "../replitAuth";

export function registerExamScheduleRoutes(app: Express): void {
  app.get('/api/departments/public-list', async (req, res) => {
    try {
      const allDepts = await storage.getDepartments();
      res.json(allDepts.map(d => ({ id: d.id, name: d.name })));
    } catch (e) {
      res.status(500).json({ message: 'Failed' });
    }
  });
  
  // Call center login — validates code against department's stored call_center_code
  app.post('/api/callcenter/login', async (req, res) => {
    try {
      const { departmentId, code } = req.body;
      if (!departmentId || !code) return res.status(400).json({ message: 'departmentId and code required' });
      const stored = await storage.getDepartmentCallCenterCode(parseInt(departmentId));
      if (!stored) return res.status(403).json({ message: 'No call center code set for this department' });
      if (stored !== code) return res.status(403).json({ message: 'Invalid access code' });
      const dept = await storage.getDepartment(parseInt(departmentId));
      res.json({ success: true, department: { id: dept?.id, name: dept?.name } });
    } catch (e) {
      res.status(500).json({ message: 'Login failed' });
    }
  });
  
  // Set call center code — dept head / center head only
  app.post('/api/callcenter/set-code', isAuthenticated, async (req: any, res) => {
    try {
      const { departmentId, code } = req.body;
      if (!departmentId || !code) return res.status(400).json({ message: 'departmentId and code required' });
      const userId = req.user?.claims?.sub || req.user?.id;
      const user = await storage.getUser(userId);
      if (!user?.isCenterHead) {
        const dept = await storage.getDepartment(parseInt(departmentId));
        if (dept?.headUserId !== userId) return res.status(403).json({ message: 'Access denied' });
      }
      await storage.setDepartmentCallCenterCode(parseInt(departmentId), code);
      res.json({ success: true });
    } catch (e) {
      res.status(500).json({ message: 'Failed to set code' });
    }
  });
  
  // Get exam schedule for a date range
  app.get('/api/exam-schedule', async (req, res) => {
    try {
      const { departmentId, startDate, endDate } = req.query;
      if (!departmentId || !startDate || !endDate) return res.status(400).json({ message: 'departmentId, startDate, endDate required' });
      const slots = await storage.getExamScheduleSlots(parseInt(departmentId as string), startDate as string, endDate as string);
      res.set('Cache-Control', 'no-store');
      res.json(slots);
    } catch (e) {
      res.status(500).json({ message: 'Failed to fetch exam schedule' });
    }
  });
  
  // Create exam schedule slot — call center (validates code in header)
  app.post('/api/exam-schedule', async (req, res) => {
    try {
      const { departmentId, callCenterCode, ...slotData } = req.body;
      if (!departmentId) return res.status(400).json({ message: 'departmentId required' });
      const stored = await storage.getDepartmentCallCenterCode(parseInt(departmentId));
      if (!stored || stored !== callCenterCode) return res.status(403).json({ message: 'Invalid call center code' });
      const slot = await storage.createExamScheduleSlot({ ...slotData, departmentId: parseInt(departmentId) });
      res.status(201).json(slot);
    } catch (e) {
      res.status(500).json({ message: 'Failed to create slot' });
    }
  });
  
  // Update exam schedule slot
  app.put('/api/exam-schedule/:id', async (req, res) => {
    try {
      const { callCenterCode, departmentId, ...slotData } = req.body;
      if (departmentId) {
        const stored = await storage.getDepartmentCallCenterCode(parseInt(departmentId));
        if (!stored || stored !== callCenterCode) return res.status(403).json({ message: 'Invalid call center code' });
      }
      const slot = await storage.updateExamScheduleSlot(parseInt(req.params.id), slotData);
      res.json(slot);
    } catch (e) {
      res.status(500).json({ message: 'Failed to update slot' });
    }
  });
  
  // Delete exam schedule slot
  app.delete('/api/exam-schedule/:id', async (req, res) => {
    try {
      const { callCenterCode, departmentId } = req.query;
      if (departmentId && callCenterCode) {
        const stored = await storage.getDepartmentCallCenterCode(parseInt(departmentId as string));
        if (!stored || stored !== callCenterCode) return res.status(403).json({ message: 'Invalid call center code' });
      }
      await storage.deleteExamScheduleSlot(parseInt(req.params.id));
      res.json({ success: true });
    } catch (e) {
      res.status(500).json({ message: 'Failed to delete slot' });
    }
  });
}
