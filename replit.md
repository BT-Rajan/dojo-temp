# Prostho Head Manager

## Overview

Prostho Head Manager is a comprehensive multi-center, multi-department operations management system for medical institutions. It supports independent centers, each with isolated data for departments, doctors, clinics, and operations. Key capabilities include managing doctor assignments, clinic schedules, emergency walk-ins, leave tracking, and examination clinics within departments. The system features hierarchical access control for Center Heads (super admins) and Department Heads. It's designed to streamline medical administration, enhance operational efficiency, and provide detailed reporting for performance analysis.

## User Preferences

Preferred communication style: Simple, everyday language.

---

## ⚠️ CRITICAL: Center Data Isolation Rules

**Every feature, page, and API route MUST enforce center isolation. Centers are completely independent — no data from one center should ever appear in another center's views.**

### How center context is determined

- The user selects a center on the Home page (`client/src/pages/home.tsx`).
- The selected center ID is stored in `localStorage` under the key `"selectedCenterId"`.
- Every page reads this value to scope its data queries.

### The isolation chain

```
selectedCenterId (localStorage)
  └── departmentId (filtered by centerId via /api/user/departments?centerId=X)
        └── doctorId (filtered by departmentId)
              └── appointments, leaves, permissions, procedure logs, clinic assignments, etc.
```

Once departments are filtered by `centerId`, all downstream data is automatically isolated because every table links back through `departmentId` or `doctorId`.

---

### Frontend rules — every page that shows data MUST:

1. **Read the selected center from localStorage:**
   ```ts
   const centerId = localStorage.getItem("selectedCenterId") || "";
   ```

2. **Include `centerId` in the department query key and URL:**
   ```ts
   const { data: departments = [] } = useQuery({
     queryKey: ["/api/user/departments", centerId],
     queryFn: async () => {
       const url = centerId
         ? `/api/user/departments?centerId=${centerId}`
         : "/api/user/departments";
       const res = await fetch(url, { credentials: "include" });
       return res.json();
     },
   });
   ```

3. **Include `centerId` when fetching doctors directly:**
   ```ts
   const { data: doctors = [] } = useQuery({
     queryKey: ["/api/doctors", centerId],
     queryFn: async () => {
       const url = centerId
         ? `/api/doctors?centerId=${centerId}`
         : "/api/doctors";
       const res = await fetch(url, { credentials: "include" });
       return res.json();
     },
   });
   ```

4. **Filter any list data client-side when centerId is known:**
   ```ts
   const centerDoctorIds = new Set(doctors.map(d => d.id));
   const centeredItems = allItems.filter(item =>
     !centerId || centerDoctorIds.has(item.doctorId)
   );
   ```

5. **Always include `centerId` in TanStack Query keys** so switching centers automatically triggers fresh fetches (cache miss → new request).

---

### Backend rules — every new API route MUST:

1. **Accept and respect `centerId` as a query parameter** when returning lists of departments, doctors, or any entity that chains through them.
2. **Use the scoped storage methods** — prefer `getDoctorsByCenter`, `getDepartmentsByCenter`, `getLeavesByDepartment`, `getActiveLeavesByDepartment`, `getPermissionsByDepartment`, etc. over the global `getDoctors()`, `getLeaves()`, `getPermissions()` methods.
3. **Never call global getters without a scope** in routes that are visible to non-center-head users. Global getters (no parameters) are only acceptable for Center Head-only endpoints.
4. **When adding new tables** that contain center-scoped data, always include a `department_id` or `center_id` foreign key and add corresponding filtered storage methods.

---

### New feature checklist

When adding any new page, component, or API route, answer these questions:

- [ ] Does this page show a list of departments? → Use `?centerId=X` in the fetch.
- [ ] Does this page show a list of doctors? → Use `?centerId=X` in the fetch.
- [ ] Does this page show appointments, leaves, permissions, schedules, stats, or procedure logs? → Ensure the `departmentId` used to fetch them comes from the center-filtered department list.
- [ ] Does the TanStack Query key include `centerId`? → It must, so switching centers invalidates the cache.
- [ ] Does the backend route accept a scope parameter (`centerId` or `departmentId`)? → It must.
- [ ] Does the backend call a scoped storage method (not a global getter)? → It must.

---

### Pages already following this pattern (reference implementations)

| Page | centerId usage |
|------|---------------|
| `home.tsx` | Source of truth — sets `selectedCenterId` in localStorage |
| `department-statistics.tsx` | `?centerId=X` on department fetch |
| `department-monitoring.tsx` | `?centerId=X` on department fetch |
| `reception-desk.tsx` | `?centerId=X` on department fetch |
| `appointments.tsx` | `?centerId=X` on doctor fetch + client-side appointment filtering |
| `dashboard.tsx` | `?centerId=X` on department fetch |
| `admin.tsx` | `?centerId=X` on doctor and user fetches |

---

## System Architecture

### UI/UX Decisions
The frontend is built with React 18 and TypeScript, utilizing Wouter for routing and TanStack Query for state management. Radix UI components with shadcn/ui provide a modern design system, styled with Tailwind CSS and custom CSS variables for theming. The application features a medical-themed aesthetic with modern styling elements like gradient backgrounds and glass effects on key pages.

### Technical Implementations
The backend uses Node.js with Express.js and TypeScript. Drizzle ORM is used for PostgreSQL database interaction, with Neon Database as the serverless provider. Session management is handled by `connect-pg-simple` for PostgreSQL session storage. The system supports multi-center and multi-department operations with complete data isolation, ensuring each center and department operates independently.

### Startup Migrations
`server/index.ts` runs `runSchemaMigrations()` on every startup using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. When new columns are added to the schema, they must also be added to this function so production deployments automatically apply the schema change without data loss.

### Overtime Procedure Logs & Stats (2026-04)
- **New table**: `overtime_procedure_logs` — one log per overtime session (UNIQUE on `sessionId`), stores same 23 procedure fields as `procedure_logs` plus `sessionDate`, `doctorId`, `departmentId`.
- **Upsert behavior**: `POST /api/overtime/procedure-logs` creates or updates the log for a session.
- **Stats route**: `GET /api/overtime/stats?departmentId=X&startDate=Y&endDate=Z&doctorId=W` returns per-doctor totals, department totals, and daily breakdown — same shape as the regular stats.
- **Frontend**: "Log" / "Logged" button on each session row in the schedule. Opens a procedure dialog pre-filled with existing data. "Overtime Stats" tab shows the same stat panels as the regular department-statistics page (summary cards, top procedures bar, daily chart, per-doctor table).
- **Who can log**: The session's assigned doctor (via doctor-login) or the department head.
- **Startup migration**: `CREATE TABLE IF NOT EXISTS overtime_procedure_logs` added to `runSchemaMigrations()`.

### Examination Scheduler / Call Center Portal (2026-04)
- **Tables**: `exam_schedule_slots` (departmentId, appointmentDate, slotTime, status, patientName, patientPhone, patientFileId, doctorName, notes, blockReason) and `call_center_code` column on `departments`.
- **Time slots**: 10-minute slots from 08:00 to 14:00 (36 slots/day), Sunday–Thursday weekly grid.
- **Access**: Call center staff log in at `/callcenter-login` using department + access code → stored as `callCenterUser` in localStorage. Doctors see read-only view via `/exam-schedule?dept=X`. Main-app users see read-only "Exam Schedule" card on home page.
- **Call center operations**: Add patient (name, phone, file ID, doctor, notes), edit/delete appointment, block single slot, bulk-block a time range, unblock.
- **Admin controls**: Department heads / center heads can set the call center access code via the "Call Center Access Code" card on the home page. The code is stored in `departments.call_center_code`.
- **Center isolation**: Slots are scoped by `departmentId` which chains to `centerId`.
- **Routes**: `GET /api/departments/public-list`, `POST /api/callcenter/login`, `POST /api/callcenter/set-code`, `GET/POST /api/exam-schedule`, `PUT/DELETE /api/exam-schedule/:id`.
- **Startup migration**: `ALTER TABLE departments ADD COLUMN IF NOT EXISTS call_center_code text` and `CREATE TABLE IF NOT EXISTS exam_schedule_slots` added to `runSchemaMigrations()`.
- **Navigation**: "Call Center" button on landing page, "Exam Schedule" button on doctor dashboard, "Exam Schedule" card on home page, "Call Center Access Code" card on home page (dept heads only).

### Overtime Portal (2026-04)
- **Tables**: `overtime_sessions` (departmentId, clinicName, doctorId, sessionDate, isOpen, notes) and `overtime_slot_entries` (sessionId, timeSlot, patientName, civilId, phone, procedure, notes).
- **Time slots**: 14:00–15:00, 15:00–16:00, 16:00–17:00, 17:00–18:00 (fixed).
- **Access**: Both doctor-login users (localStorage `doctorUser`) and main auth users can use the portal at `/overtime`.
- **Admin controls**: Department heads (where `department.headUserId === user.id`) can add sessions, toggle open/close, and delete sessions.
- **Center isolation**: Sessions are scoped by `departmentId` which chains to `centerId`.
- **Routes**: `GET/POST /api/overtime/sessions`, `PATCH/DELETE /api/overtime/sessions/:id`, `GET/POST /api/overtime/slots`, `PUT/DELETE /api/overtime/slots/:id`.
- **Startup migration**: Both tables created with `CREATE TABLE IF NOT EXISTS` in `runSchemaMigrations()`.
- **Navigation**: "Overtime" button on doctor dashboard; "Overtime Portal" card on home page.

### Feature Specifications
- **Multi-Center Support**: Create and manage multiple independent medical centers with separate data and processes.
- **Doctor Management**: Full CRUD, availability tracking, and personalized dashboards.
- **Clinic Assignment System**: Weekly recurring schedules, multi-day assignments, and visual management.
- **Emergency Management**: Fair rotation for walk-ins, automatic doctor suggestions, and historical tracking.
- **Leave & Permission Tracking**: Management of leaves (annual, sick, emergency) and partial-day permissions.
- **Examination Clinic Management**: Specialized slots with capacity limits and multi-doctor assignments.
- **Patient Appointment System**: Comprehensive calendar, time-based scheduling, and full appointment management (create, edit, delete).
- **Department Head Monitoring**: Dashboard for overseeing doctor performance, appointments, and statistics with filtering and date range analysis.
- **Doctor of the Month System**: Performance-based ranking, award creation, and certificate generation.
- **Comprehensive Reporting**: Department statistics page with procedure-based reporting, filtering, and export capabilities.
- **Procedure Logging**: Doctors fill a questionnaire after completing appointments, logging dental procedures including: Alginate Preparation, Crown/Bridge Preparation, Final Impression, Temp/Permanent Cementation, Post Preparation/Canal, Composite/Amalgam Filling, Removable Prostho, Ortho Appliances, Buckle Appointment, Implant Units, Try-In, Miscellaneous, Examination.

### System Design Choices
The application is structured as a full-stack web application. Data is rigorously filtered by `departmentId` and `centerId` across both frontend and backend to enforce data isolation. Authentication handles both Replit and local accounts. The build process leverages Vite for the frontend and esbuild for the backend, optimizing for fast development and efficient production deployments.

## External Dependencies

- **@neondatabase/serverless**: Serverless PostgreSQL database connection.
- **drizzle-orm**: Type-safe database ORM.
- **@tanstack/react-query**: Server state management and caching.
- **@radix-ui/react-***: Headless UI components.
- **react-hook-form**: Form management and validation.
- **zod**: Runtime type validation.
- **date-fns**: Date manipulation utilities.
- **connect-pg-simple**: PostgreSQL session storage.
