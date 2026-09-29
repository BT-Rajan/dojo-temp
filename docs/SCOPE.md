# Elite Academy System — Scope of Work

| Field | Detail |
|---|---|
| Document Number | EA-SYS-SCOPE-01 |
| Title | Elite Academy System — Scope of Work |
| Version | 0.6 (Draft for review) |
| Date | 29-Sep-2026 |
| Document Owner | Systems & IT Lead |
| Reviewed By | Operations Lead (COO); Training Lead; Marketing Lead |
| Approved By | Chief Executive Officer |
| Related Documents | EA-SYS-SEC-01 ISO 27001 Control Mapping (docs/security/ISO27001_CONTROLS.md); EA-SYS-SEC-02 RBAC Matrix (docs/security/RBAC_MATRIX.md); EA-SYS-DESIGN-01 Website Design Brief (docs/WEBSITE_DESIGN_PROMPT.md); EA-OPS-PROC-01 Operations Procedure; EA-INV-PROC-01 Inventory Management Procedure; EA-COMM-PROC-01 Communication Procedure; EA-COMM-PLAY-01 How We Work Together; EA-COMM-REF-01 Org Chart; Customer Management Procedure & One Voice Guide; Marketing Funnel by Branch; Kajukenbo Master Curriculum; Active Members Report (EA-DOC-003) |

**Change log**

| Version | Date | Change |
|---|---|---|
| 0.1 | 28-Sep-2026 | First draft from Elite procedures, reports and meeting notes. |
| 0.5 | 29-Sep-2026 | Phase 3 started at the CEO's request; Phase 2 demo and every open decision gathered in Section 8.1, to be closed one by one at the end of the project. Phase 3 working decisions P3-1 to P3-10. |
| 0.6 | 29-Sep-2026 | Phase 3 built in test. Phase 4 (Training and Progression) started; working decisions P4-1 to P4-10; open items O-18 and O-19. |
| 0.4 | 29-Sep-2026 | Phase 1 signed off. Phase 2 decisions P2-1 to P2-17 recorded: pay options for any staff member or coach, OM prepares and Accountant approves payroll, freelance coaches paid through payroll, report layouts from the current forms. |
| 0.3 | 28-Sep-2026 | Added Section 11 Technology and Non-Functional Requirements: Python (Django) back end, MySQL 8 database, front end from the Claude Design template; many simultaneous users; ISO/IEC 27001:2022 alignment; role-based access control. Phase 0 built on the new stack; the clinic codebase becomes a reference only (Section 10). |
| 0.2 | 28-Sep-2026 | Added: website content management (CMS) with events photo gallery (M14); online shop for equipment (M19); payroll for directly hired coaches and staff (M20); Kuwait test data package (M21); first run, test and change requests (Section 7.1). Payroll and online shop moved out of "Out of Scope". |

---

## 1. Purpose

Elite Academy runs today on Mindbody (sales, bookings, stock), SAQR (WhatsApp AI and leads), a website admin panel, paper forms, Excel sheets and the shared drive. The same fact is typed into three places, weekly reports are rebuilt by hand, and signatures live on paper.

This document defines **one system that replaces Mindbody and turns every Elite procedure into software**: every form becomes a screen, every signature becomes a recorded confirmation, and every report builds itself from the data.

**Goal:** every member at either branch gets the same Elite experience — a clean, open dojo, a correct membership status, a fast reply, and an accurate record of every payment, item and promotion — with the procedures enforced by the system instead of by memory.

## 2. Guiding Principles

These come straight from Elite's own documents and shape every screen:

1. **"The next person accepts the handoff before we let go."** Every handoff in the system (transfer, report, cascade, lead, complaint, cover) has a *sender* and a *receiver who confirms*. Nothing is complete until it is confirmed.
2. **One source of truth.** Schedule, prices and programs are entered once. The website, the SAQR chat, the member portal and the front desk all read the same data — no more "update Mindbody, the website and SAQR at the same time."
3. **Roles by designation, not by person.** Permissions attach to roles (Branch Admin, Operations Manager…), so the system stays valid when people change.
4. **Safety first.** Incidents, child safeguarding and escalations have their own fast path with 24-hour deadlines tracked by the system.
5. **Every lead, request and concern has one owner and a next action.**
6. **Branch isolation is enforced by the server**, not by the browser. A Bedaya login cannot see or change Promenade data unless its role allows it.
7. **Bilingual.** Arabic and English throughout (right-to-left layout for Arabic), because the One Voice guide requires replying in the client's language.
8. **Local by default.** Kuwaiti Dinar with 3 decimals, KNET / Visa-MC / Cash, Civil ID, Saturday–Friday reporting week, Kuwait time.

---

## 3. Users and Roles

| Role | Held by (today) | Main use of the system | Data scope |
|---|---|---|---|
| **CEO** | Dakhil | Dashboards, quarterly report, approvals of procedures, safety escalations, direct-line messages | Both branches, read everything |
| **Operations Manager (COO)** | Nasser | Verify weekly reports, approve purchases / price changes / freezes / refunds / stock corrections, assign owners, cover & handover | Both branches |
| **Training Lead** | Abdullah | Programs, curriculum, instructor management, evaluations, promotions, attendance trends | Both branches, training data |
| **Track Lead** | Carlos (grappling), Ahmed (striking) | Curriculum for their track, evaluations, test days | Both branches, their track |
| **Instructor** | All instructors | Class rosters, attendance, trial briefs, evaluations, test results, incident reports | Their classes |
| **Marketing Lead** | Maryam | Campaigns, funnel, group sales, knowledge base (voice & content), **website CMS: approves publishing**, gallery | Both branches, marketing data (no payments) |
| **Marketing Implementation** | Ayaa | Campaign tracker, consented media library, **website CMS: drafts pages, news and gallery albums** | As Marketing Lead, no approvals |
| **Systems & IT Lead** | Saud | Users, roles, settings, integrations, AI configuration, audit log, data imports | System-wide admin |
| **Branch Admin** | Verna (Promenade), Tareq (Bedaya) | Front desk: check-in, trials, registration, sales, renewals follow-up, class changes, daily/weekly forms, stock | Own branch (plus "both branches" duties where the playbook assigns them) |
| **Operations Support / Coach** | Roaa | Front desk duties at either branch + instructor duties; handles AI handoffs | Both branches; instructions visible to both her leads |
| **Purchasing / Receiving Coordinator** | (Promenade) | Place approved orders, receive deliveries, discrepancy reports | Inventory, both branches |
| **Accountant** | (new user) | Cash-up and settlement reconciliation, expenses, income statements, **monthly payroll preparation**, exports | Financial and payroll data, both branches, read-only on members |
| **Member / Parent** | Clients | Portal: schedule, bookings, payments, renewals, progress, consent, family | Own family only |
| **Public visitor / online customer** | Anyone | Website, gallery, schedule, prices, trial booking, SAQR chat, online shop | Public info and own orders |

A person can hold more than one role (Roaa is Operations Support **and** Instructor). Every action records *who* did it and *in which role*.

---

## 4. Modules

Each module lists what it does and which existing Elite form or procedure it replaces.

### M1. Branches, Programs and Pricing
*Replaces: Mindbody pricing options and the ">12 KD" rule.*

- **Branches:** Promenade (Hawalli) and Bedaya (Sabah Al Salem), each with address, opening days, local details (parking, mall directions) and its own marketing positioning.
- **Disciplines / programs:** Shin-Kyokushin, Kyokushin Karate, Kajukenbo, Kickboxing, Taekwondo, Jiu-Jitsu, Elite Promenade All-Access, Grappling, Striking, Ladies' class, Systema, and any future program. Each has age groups (e.g. 5–7, 8–12, 13+, adults), gender (e.g. ladies' class) and branch.
- **Pricing options** with an explicit **type** instead of a price threshold:
  - *Membership* (counts as an active member): monthly plans, session packages (10×4, 12×5, 12×6), 3-month plans, All-Access.
  - *Non-membership*: Trial Pass (10 KD), Day Pass, Private Session, Seminar, Camp, Event (e.g. Elite Games), Systema.
- Price, duration or session count, program(s) covered, age group, branch, active dates.
- **Discounts and special rates:** family / sibling bundle, Elite Member tier (competitors who attend daily), referral reward, promotional trials (e.g. "free until 31 Aug").
- **Price changes require Operations Manager approval** before they go live anywhere (replaces the FRM-05 approval rule).

### M2. Members and Families
*Replaces: Mindbody client profiles, EA-OPS-FRM-03 Registration Form, EA-MKT-FRM-01 Media Consent Form.*

- Member profile: name (Arabic/English), date of birth, Civil ID, gender, branch, mobile/WhatsApp, email, photo, source ("how did you hear about us").
- **Family accounts:** one parent/guardian linked to several children; the guardian pays, books and consents for them.
- Emergency contact and relationship; **medical conditions, injuries, allergies** (visible to the member's instructors, restricted from marketing).
- **Media consent** captured digitally at registration with the three tick-boxes from EA-MKT-FRM-01 (internal records / social media / website & marketing), signed on screen, withdrawable at any time, with history.
- Agreement to rules and safety instructions, signed on screen.
- Membership history, visits, payments, belt/rank, evaluations, incidents and complaints on one timeline.
- Member status is **calculated, not typed**: Active / Expiring (≤5 days) / Expired / Frozen / Trial / Lead / Former.

### M3. Leads, Trials and Sales Pipeline
*Replaces: SAQR lead records, the Individual Membership Journey, the Group Sales process.*

- **Every lead recorded with:** name, contact, source/campaign, branch/interest, **one named owner**, stage, next action and due date. *Tie-breaker built in: whoever first contacts the lead becomes its owner* (resolves Playbook open item 2).
- Stages: Inquiry → Contacted + Trial Booked → Trial Delivered → Paid Membership → Renewal; plus Lost (with reason).
- Leads arrive from: walk-in (front desk), SAQR chat (website / WhatsApp), website trial form, phone, referral, group sales.
- **Trial booking with name and phone only** (per the marketing audit — no account before the trial). Account is created when they join.
- Trial brief sent to the class instructor automatically; instructor records attendance and feedback; front desk follows up within 24 hours.
- **Group sales pipeline** (schools, companies): Contact → Meeting → Proposal → Agreement → Paid registrations → Delivery handoff, with a named receiving owner in Operations who confirms before Training delivers (resolves Playbook open item 1 once the owner is named).
- Conversion reports per stage, per owner, per branch and per campaign.

### M4. Classes, Schedule, Bookings and Attendance
*Replaces: Mindbody schedule and check-in, EA-OPS-FRM-04 Class Change Notice Log.*

- **Weekly class timetable** per branch: program, age group, day, start/end, room, instructor(s), capacity. Supports the alternating patterns in the curriculum (Striking / Grappling rotation, Sat-Mon-Wed vs Sun-Tue-Thu).
- **Bookings** by front desk, member portal or trial request; waitlist when full.
- **Check-in** at the front desk (search or scan member QR code) or by the instructor from the class roster on a tablet/phone.
- **Class changes** (cancel / reschedule / substitute instructor): approved by Training Lead or OM → every booked and regular member notified automatically by WhatsApp/SMS → log records time, channel and number notified. The website and SAQR update automatically because they read the same schedule.
- **Seminars, camps, events and private sessions** as bookable sessions (needed for Kajukenbo seminar points and summer camps).
- Instructor view: today's classes, roster with photos, medical flags, trial students, attendance taking.
- Class utilisation (booked vs capacity) and visit trends.

### M5. Point of Sale, Payments and Receipts
*Replaces: Mindbody point of sale (Guide G3), cash handling rules.*

- Sell memberships, packages, Trial Pass, Day Pass, sessions, events and **retail items by exact size** from the member's profile.
- **Free issue** (e.g. grading belt) at 0 KD so stock still reduces — linked automatically to belt promotions (M7).
- Payment methods: **KNET, Visa/MC, Cash**, and online payment through the portal (gateway to be chosen — see Section 8).
- Printed / WhatsApp / email receipt for every sale, numbered per branch.
- Sale categories assigned automatically: **New, Renew, Trial Pass, Day Pass, Equipment** (the FRM-06 mapping).
- **Rules enforced:** no item handed over without a sale; no "miscellaneous" item; no selling the other branch's stock; sale must be at the logged-in branch.
- **Freeze, refund and cancellation requests** are logged by the admin and approved by the OM (admins cannot approve). Freeze fee applied when set (Playbook open item 3).
- **End-of-day cash-up:** counted cash vs system cash, KNET and card totals vs terminal settlement, differences recorded and sent to the OM and Accountant.

### M6. Renewals and Retention
*Replaces: EA-OPS-FRM-02 Membership Expiry & Renewal Follow-up List, Guide G2.*

- **Daily follow-up list built automatically** for each branch: (a) expired within the last 30 days, (b) expiring within 5 days — excluding trials, passes, camps, seminars and private sessions, and skipping anyone who already renewed.
- Contact from the list (WhatsApp one-tap with One Voice renewal template, or call) and record outcome: **R** Renewed · **W** Will renew (date) · **F** Freeze requested · **L** Leaving (reason) · **N** No answer (attempt 1/2/3).
- "No answer" carries to the next shift; **after 3 attempts the member is passed to their instructor** for a personal word at class.
- Automatic renewal reminders to members/parents before expiry (configurable days).
- **At-risk list:** active members with no visit in X days (the "No visit found" check from the Active Members report).
- "Leaving" reasons feed the weekly report and churn analysis.

### M7. Training, Curriculum and Progression
*Replaces: Kajukenbo Master Curriculum workbook, 4–6 week evaluations, test-day records.*

- **Curriculum builder** per art: ranks (belts), stripes, and the skills required at each level, grouped by track (Kickboxing, Jiu-Jitsu, Self-Defence & Traditional, Fitness). The Kajukenbo scalable curriculum is loaded first: *one belt (Kajukenbo + Kickboxing level), one stripe (BJJ level), seminar points*.
- Other arts (Kyokushin, Taekwondo, etc.) get their own belt systems in the same structure.
- **Member progress card:** current belt and stripe, skills checked off, seminar points earned, attendance count, next requirements.
- **Evaluations every 4–6 weeks:** instructor scores against the level's skills with notes; the system reminds instructors when evaluations are due.
- **Test days:** list eligible students (attendance + seminar points + evaluations), record the result per component (kickboxing, jiu-jitsu, seminar points check, self-defence demo), and promote. Promotion issues the belt from stock as a free issue (M5/M8) and can trigger a parent message and a Google review request (M13).
- **Tournament eligibility** shown per student (striking level, BJJ-equivalent stripe, Kajukenbo rank).
- Instructor access to the right track sheet for their classes, so hourly instructors can teach from it (the "How It Scales" model).
- Monthly progress note to parents ("what your child worked on, what's next") — from the retention funnel.

### M8. Inventory, Purchasing and Vendors
*Replaces: Mindbody inventory, EA-INV-PROC-01 and forms FRM-01/03/04/05, EA-PO purchase orders, EA-OPS-FRM-08 Monthly Count, the Sept 2026 physical-vs-Mindbody workbooks.*

- **Product catalogue** with variants (item × size × colour), barcode, supplier, cost, retail price, reorder level, max level, program (or "no program"), and an "old stock / no logo" flag.
- **Stock on hand per branch**, with a full change log (who, when, why) for every movement.
- **Purchase Request (FRM-05):** branch admin requests items by size with reasons → OM approves / rejects / amends **within 2 business days** (reminders and overdue flag) → requester notified with the reason. **Local requests limited to one per branch per month** — enforced by the system.
- **Purchase Order (EA-PO):** generated from the approved request, numbered EA-PO-YYYY-NNN, sent to the vendor (Arabic or English template).
- **Receiving (FRM-01) at Promenade:** check delivery against invoice and approved request per item and size → record what actually arrived → stock increases at Promenade automatically. Invoice attached.
- **Missing / Discrepancy Report (FRM-04):** created from the receipt when quantities differ; vendor and OM notified; tracked until resolved.
- **Internal Transfer (FRM-03):** sender creates and confirms → receiver counts and **accepts** → only then does stock move between branches. A mismatch cannot be accepted without calling the sender and OM.
- **Monthly count (FRM-08):** count sheet generated per branch on the last working day; two-person count entry (counter + recorder); recount of every difference; reason codes **US, UT, D, FI, EE, U**; OM approval before stock is corrected; items short two months running flagged. Due by the 3rd working day.
- **Vendors:** local and international, contacts, quotations, orders, invoices, payments, status.
- **International order costing:** landed cost calculator (unit price, exchange rate, freight, customs/clearance %) and target-margin counter-price (the Dhalay analysis), saved with the order.
- Reorder suggestions from stock levels and sales rate.

### M9. Daily Operations
*Replaces: EA-OPS-FRM-01, FRM-05, FRM-09, FRM-10, FRM-11.*

- **Shift opening checklist (FRM-01)** on screen, with the 9 checks, completed and signed before the first class; hazards raised go straight to the OM.
- **Incident report (FRM-09):** injury / safety hazard / conduct / other; child incidents require guardian notification time; OM notified the same day; **CEO escalation countdown of 24 hours** for safety or removal decisions; follow-up owner and closure.
- **Complaint log (FRM-10):** from desk, WhatsApp, SAQR or call; One Voice complaint opener shown to the admin; auto-escalation to OM for money, refunds, staff conduct, safety or threat to leave; **reply to member within 24 hours** tracked; closed only when the member is told the outcome.
- **Cover & Handover (FRM-11):** OM names cover in writing; the system builds the open-items list automatically (cash held, pending payments, open follow-ups, leads and trials, complaints, incidents, purchase requests, transfers, stock count status); the incoming person accepts each item; departing staff access removed on their last day.
- **Website update log (FRM-05)** is no longer needed as a separate step because the website reads from the system; every change is still recorded in the audit log.
- **Task list** for every role: all open items assigned to me, with due dates (follow-ups, approvals, handoffs, escalations).

### M10. Reports and Dashboards
*Replaces: EA-OPS-FRM-06, FRM-07, Active Members Report (EA-DOC-003), EA-OPS-RPT-01, the Mindbody Reporting Cadence.*

All reports are generated from live data, can be filtered by branch / program / date, show Promenade, Bedaya and Combined, and export to PDF and Excel. Reports that need sign-off follow the prepare → verify flow with names and dates.

| Report | Built from | Cadence | Sign-off |
|---|---|---|---|
| **Active Members** (unique members, by program, by branch, verified by attendance, week-over-week change, roster per program) | Memberships + visits | Live; weekly snapshot every Friday | — |
| **Weekly Sales Report (FRM-06)** — every transaction, category, method, totals, expenses, net income | Sales + expenses | Sat–Fri, due Sat 12:00 | Admin prepares, OM verifies |
| **Weekly Branch Report (FRM-07)** — active members, new, trials booked/attended/converted, renewals, members lost, incidents, complaints, class changes, open items | All modules | Weekly | Admin prepares, OM verifies |
| **Monthly Count & Variance (FRM-08)** | Inventory | Monthly | Admin, OM approves |
| **Quarterly Business Report (RPT-01)** — all 11 sections: summary, next-quarter strategy, KPIs, sales analysis, capacity, footfall, new clients, renewals & churn, incidents & complaints, inventory, income statement | Verified weeklies + accounts | Quarterly, due 15 days after quarter end | OM → CEO |
| Daily dashboard: visits, no-shows, class fill, sales snapshot, cash-up status | Live | Daily | — |
| Weekly: new vs returning, cancellations, revenue mix, leads by stage | Live | Weekly | — |
| Monthly: sales growth, membership growth / churn, cross-branch comparison, instructor hours, inventory | Live | Monthly | — |
| Training: attendance per class and instructor, evaluations due/done, promotions, belt distribution | Training data | Monthly (Training Lead → CEO) | — |
| Marketing: campaign results, cost per lead / conversion, funnel by branch | Leads + campaigns | Monthly (Marketing Lead → CEO) | — |

Reports can be scheduled to be emailed automatically. Form reference numbers follow Elite's scheme, e.g. **FRM-06-BED-2026-012**.

### M11. Finance and Accounting
*New: the Accountant role.*

- Daily cash-up and settlement reconciliation (KNET, card, cash) per branch, with differences flagged.
- Branch expenses with receipt photos, categories and approval.
- Refunds and freeze fees with approval trail.
- Revenue by category (services vs products), by program, by branch, by month.
- **Monthly and quarterly income statement** ("for the quarter ended"), with the rule that headline sales must agree with trading income or the difference is explained.
- Vendor invoices and payments (international and local), landed cost records.
- Export to the accountant's tool (Excel / CSV; direct integration to be decided — see Section 8).

### M12. Communication and Management
*Replaces: EA-COMM-PROC-01 mechanics, the Monthly Leads Meeting MOM template, the escalation logs.*

- **Announcements / cascade:** a decision from the CEO (or a lead) is posted once, sent to the named leads, forwarded **unchanged** to their teams; each person confirms receipt; the sender sees who has not confirmed; **2-working-day cascade deadline** with reminders.
- **Handoff requests between leads** (e.g. Training → Marketing progress stories, Marketing → Operations leads, any lead → Systems & IT requests) with receiver confirmation and, for IT, a committed timeline.
- **Dual reporting line:** instructions to someone with two leads (Roaa) are automatically visible to both leads (resolves Communication open item 1).
- **Monthly leads meeting:** agenda, attendance, discussion, decisions (with owner) and action items (owner, due date, status) — action items flow into owners' task lists.
- **Upward reports:** monthly summaries from each lead to the CEO, pre-filled from the system's data.
- **Escalation log** for safety and conduct concerns, with the 24-hour rule, and the "call Dakhil directly" route recorded.
- **Procedure library:** every procedure, form and policy with version number, effective date, owner and approval status; staff confirm they have read new versions.
- **Staff directory and org chart** generated from roles and reporting lines.

### M13. Marketing
*Replaces: Campaign Tracker (Playbook §8), consent audit, referral handling.*

- **Campaign tracker:** name, channel, start/end, spend; leads and conversions counted automatically from lead sources; **cost per lead** and **cost per conversion** calculated (resolves Playbook open item 5).
- **Media library with consent check:** photos/videos tagged with the members in them; the system shows which uses each member's consent allows and blocks the rest; consent withdrawal flags existing posts for review (resolves Playbook open item 4).
- **Referral program:** referral links/cards per member, reward tracking (free month or gear credit).
- **Review requests** after strong trials and belt promotions.
- Funnel dashboards by branch (Promenade and Bedaya run different funnels).
- WhatsApp broadcast lists (with opt-in) for campaigns and announcements.

### M14. Public Website and Content Management (CMS)
*Replaces: the current website admin panel and EA-OPS-FRM-05 Website Update Log.*

**The public website (reachable by clients)**
- Home, About (vision "We build better humans", the five principles), each branch, each program, schedule, prices, instructors, events, gallery, news, shop, contact, and trial booking.
- Branch pages with their own positioning ("Complete Fighter Program" at Promenade; "Choose Your Discipline" and the ladies' class at Bedaya).
- Programs, schedule and prices shown **live from the system** — never typed into the CMS.
- **Book a trial** with name and phone only → becomes a lead with an owner.
- **SAQR chat window** on every page (M16).
- Arabic and English with right-to-left layout, mobile first, fast on phones, search-engine friendly (e.g. "martial arts Hawalli"), Google Business Profile links.

**Content management (CMS) for staff**
- Edit pages from ready-made blocks (hero, text, image, video, program cards, instructor cards, testimonial, call to action, FAQ, map) — no coding.
- Every page and block has Arabic and English versions side by side.
- **Draft → review → publish:** Ayaa (or any content editor) drafts; the Marketing Lead approves and publishes; scheduled publishing and unpublishing (e.g. a promotion that ends on 31 Aug).
- Version history for every page, with one-click restore.
- News / announcements and **events** (seminars, camps, tournaments, showcases, Elite Games) with date, branch, description and a registration or trial link.
- Homepage banners and promotions with start and end dates.
- Instructor profiles managed in the CMS, linked to the instructor's record.
- SEO fields (page title, description, share image) per page and language.
- Every published change is recorded in the audit log (replaces the FRM-05 log).

**Events photo gallery**
- Albums per event (e.g. "Summer Camp 2026", "Kajukenbo Seminar – Oct", "Belt Test – Bedaya"), with date, branch, program and cover photo.
- Bulk upload of photos and short videos; automatic resizing and watermark option.
- **Consent check before publishing:** members in each photo are tagged; a photo can only go public if every tagged member's consent covers "website and marketing" (EA-MKT-FRM-01). Untagged photos of children cannot be published until reviewed.
- If a member withdraws consent, every public photo they appear in is hidden automatically and flagged for review.
- Parents can see private albums of their own children's events in the member portal (M15), even where public consent is not given.
- Gallery photos can be reused in news posts, event pages and social media from the same media library (M13).

### M15. Member and Parent Portal
*New.*

- Sign in by mobile number (one-time code).
- Family view: each child's schedule, bookings, attendance, membership status and expiry.
- **Book and cancel classes** within the rules; join waitlists.
- **Renew and pay online**; view receipts and payment history.
- Request a freeze (goes to OM approval).
- **Progress:** current belt, skills achieved, next belt requirements, evaluation notes, seminar points, test dates.
- Manage media consent and contact details; sign forms digitally.
- Notifications: renewal reminders, class changes, trial confirmations, test days, monthly progress notes.

### M16. AI Assistants and Knowledge Base
*Replaces and extends SAQR.*

**Knowledge base (one source for both assistants)**
- Programs, schedules and prices come live from the system; everything else is written articles: FAQs, trial terms, branch details, the One Voice guide, policies, and every procedure and system guide.
- Owned by named editors (Marketing for public content, Operations and Systems & IT for internal content); every article is versioned; public and staff-only articles are separated.

**SAQR — public chat on the website (and later WhatsApp)**
- Answers program, schedule, price, location and "which branch is right for me" questions in the One Voice tone, in the client's language.
- Captures trial requests (name + phone) and creates a lead automatically.
- **Hands over to a human immediately** — with the full chat history — when the message mentions refund, cancel, complaint or injury, when the client asks for a person, or after two unresolved exchanges. The handoff lands in the front desk's queue with an owner.
- Never handles payments, approvals or complaints itself.
- Staff can review conversations and spot-check answers (≥3 per shift, per the procedure); wrong answers are corrected in the knowledge base.

**Staff Assistant — inside the app**
- "How do I…?" questions answered from the procedures and system guides (e.g. "how do I transfer stock to Bedaya?").
- **Data questions answered from live data**, e.g. "How many active members are in Kajukenbo at Bedaya?", "Who is expiring this week?", "What were last week's KNET sales at Promenade?"
- Read-only, and **limited to what the asking user's role and branch are allowed to see**.
- Shows where each answer came from (report, record or article) so staff can check it.

### M17. Notifications and Messaging
- Channels: WhatsApp (WhatsApp Business API), SMS, email, in-app.
- Member messages: trial confirmation, class changes, renewal reminders, receipts, progress notes, test days.
- Staff alerts: approvals waiting, overdue follow-ups, escalations, handoffs to accept, reports due.
- Templates in Arabic and English, written from the One Voice guide.

### M18. System Administration, Security and Data
- Users, roles, branch access, and multi-role staff.
- **Audit log** of every create, change and delete (who, when, what, before/after).
- Server-side permission checks on every action (fixes the security gaps found in the current code).
- Protection of sensitive data: children's records, Civil IDs, medical information — restricted by role, encrypted in storage, never shown to marketing.
- **Record retention** per EA-OPS-PROC-01 §8 (e.g. weekly sales 5 years, registration while active + 2 years, quarterly reports permanent).
- Daily backups; data export.
- **Mindbody data import** (Section 6).

### M19. Online Shop (E-commerce)
*New — sells equipment online from the same stock as the front desk.*

- **Catalogue from inventory (M8):** products, sizes, colours, photos and prices are the same records the front desk sells; online prices can differ only with OM approval.
- Shows only what is in stock; stock is reserved when an order is placed and reduced when it is fulfilled, from the branch that fulfils it — the monthly count stays correct.
- **Size guides** per product (gloves in oz, uniforms in cm, guards XS–XL) and program kits (e.g. "Kajukenbo starter kit": uniform + gloves + shin guards).
- Member prices and bundles (e.g. new-member kit discount), and gear credit from the referral program.
- Cart and checkout with **KNET and Visa/MC** through the chosen gateway; guest checkout or member login.
- **Fulfilment:** pick up at Promenade or Bedaya (ready-for-pickup message), or home delivery within Kuwait by area with delivery fees (courier to be chosen).
- Order statuses: Paid → Preparing → Ready for pickup / Out for delivery → Completed; cancellations, returns and exchanges (e.g. wrong size) with OM approval for refunds.
- Order confirmation, invoice and status updates by WhatsApp / email in Arabic and English.
- Online sales appear in the Weekly Sales Report (category Equipment, channel Online) and in finance reports.
- Belts are **not** sold online — they are issued only through promotion (M7).
- Phased: the provision (data model, catalogue, stock reservation) is built with inventory in Phase 3; the storefront opens in Phase 6.

### M20. Payroll and Staff (Directly Hired Coaches and Staff)
*New — replaces paying salaries outside the system.*

- **Staff records:** employment type (full-time, part-time, hourly), job title, branch, start date, contract terms, Civil ID, nationality, bank account (IBAN), and **document expiry reminders** (civil ID, residency, work permit, passport, coaching certificates).
- **Pay structures (any combination for any staff member or coach, decision P2-1):** monthly salary; allowances (e.g. transport, housing); **hourly rate or rate per class, with classes taken automatically from the ones actually taught** (M4); rates per program if needed; commission on the person's own sales by category.
- **Monthly payroll run:** the system builds the draft from classes taught, sales, leave and absences → the Operations Manager checks it, adds bonuses and deductions and submits it → the Accountant approves it (never the person who submitted it) → payslips and the bank file are released; the CEO sees the summary. No salary is paid without an approved run.
- Additions and deductions: overtime, extra classes, seminars and camps taught, bonuses (e.g. Instructor of the Month), absence deductions, salary advances and their repayment.
- **Leave:** annual and sick leave balances and requests (linked to class cover in M4); unpaid leave.
- **Kuwait rules, configurable and confirmed by the Accountant:** end-of-service indemnity accrual under the Kuwait Private Sector Labour Law, PIFSS social security contributions for Kuwaiti employees, and public holidays.
- **Outputs:** bilingual payslips (sent to staff in the app / by WhatsApp), bank salary transfer file, payroll summary per branch and per function, and payroll cost feeding the income statement (M11) and the Quarterly Business Report.
- Freelance or contracted coaches are paid in the same monthly run with the same pay options, without PIFSS, end-of-service or leave (decision P2-7).
- Payroll data is visible only to the Accountant, the Operations Manager and the CEO; each employee sees only their own payslips.

### M21. Test Data Package (Kuwait)
*New — realistic, fictional data for testing, demos and staff training.*

- **Fictional people only** — no real member, child or staff data is ever used for testing.
- Names in Arabic and English reflecting Elite's actual mix (Kuwaiti, other Arab and expatriate families), families with 1–4 children, ages 5 to adult, boys, girls, men and ladies' class members.
- **Kuwait formats:** 12-digit Civil IDs in the correct structure (century digit, date of birth, serial, check digit) that match each person's date of birth, mobile numbers in the +965 8-digit format (starting 5, 6 or 9), addresses by governorate, area, block, street and building (e.g. Hawalli, Salmiya, Jabriya, Sabah Al Salem, Mubarak Al-Kabeer).
- **Money and calendar:** Kuwaiti Dinar with 3 decimals and the real price points (85 KD Promenade, 65 KD kids / 55 KD adults Bedaya, 10 KD trial), a KNET-heavy payment mix, Saturday–Friday weeks, Friday closure, Kuwaiti public holidays, a Ramadan timetable and the summer camp season.
- **12+ months of history** so every report has data: visits, sales, renewals, freezes, leavers with reasons, trials and conversions, belt tests and promotions, campaigns and leads at every stage.
- Both branches with Elite's real programs, class timetable, pricing options and product catalogue (sizes and colours from the September 2026 count), local vendors and one international order in USD with landed cost.
- Staff for payroll testing: salaried and hourly coaches, Kuwaiti and expatriate staff (to test PIFSS and document expiry), leave balances and an advance being repaid.
- **Edge cases on purpose:** members expiring today and in 5 days, expired 15 days, frozen, active but no visit in 30 days, duplicate names, siblings sharing a guardian, a child incident, open and escalated complaints, negative stock, a delivery short-shipped, a pending transfer, a purchase request over the monthly limit, a photo with a member who has not consented, an online order returned for a wrong size.
- One-click **reset and reload** in the test environment; the package can never be loaded into the live system.
- Expected results sheet for key checks (e.g. "active members at Bedaya on the test date = 47") so testers can confirm reports are correct.

---

## 5. Business Rules the System Enforces

| # | Rule | Source |
|---|---|---|
| 1 | Active member = holds a valid, unexpired paid *membership-type* pricing option. Trials, day passes, camps, seminars, private sessions, events and Systema do not count. Counted once per person; once per program in per-program counts. | OPS-PROC §3.2, Active Members report |
| 2 | Sale category: New = first paid membership; Renew = existing/returning member; Trial Pass; Day Pass; Equipment. A trial is never recorded as a Day Pass. | OPS-PROC G4 |
| 3 | Reporting week Saturday–Friday; weekly reports due Saturday 12:00. | OPS-PROC §4 |
| 4 | Renewal follow-up covers expired (≤30 days) and expiring (≤5 days); 3 no-answers → instructor. Expired >14 days without renewal = member lost. | OPS-PROC §3.2, G5 |
| 5 | Price changes, freezes, refunds and cancellations require OM approval. | OPS-PROC §3.5, §3.6 |
| 6 | No item leaves a branch without a sale (or 0 KD free issue) or a signed transfer. | OPS-PROC §3.7, G8 |
| 7 | Purchase requests decided within 2 business days; one local request per branch per month; no order without approval. | INV-PROC §4 |
| 8 | All vendor deliveries are received at Promenade; Bedaya receives only by transfer. | INV-PROC §5 |
| 9 | Stock transfers change ownership only when the receiver accepts. | INV-PROC §6 |
| 10 | Monthly count on the last working day; due by the 3rd working day; corrections only after OM approval; reason code on every difference. | OPS-PROC §5 |
| 11 | Safety or removal matters reach the CEO within 24 hours; child incidents notify the guardian at once. | OPS-PROC §7.1, Playbook §6 |
| 12 | Complaints: logged the same day, member replied to within 24 hours, closed only when the member is told the outcome. | OPS-PROC §7.2 |
| 13 | Downward cascade completed and confirmed within 2 working days. | COMM-PROC §4.2 |
| 14 | Photos/videos used only within the member's signed consent. | Playbook §7 |
| 15 | Every lead has exactly one owner (first contact) and a next action. | Playbook §5 |
| 16 | Departing staff lose all access on their last day. | OPS-PROC §7.4 |
| 17 | A photo or video goes public only if every tagged member's consent covers that use; consent withdrawal hides it automatically. | Playbook §7 |
| 18 | Website pages publish only after Marketing Lead approval; programs, schedule and prices on the website always come from the system. | New (CMS) |
| 19 | Online orders reserve stock at order and reduce it at fulfilment, from the fulfilling branch; refunds need OM approval. | New (Shop), OPS-PROC §3.5 |
| 20 | Payroll: the OM prepares and submits, the Accountant approves (never their own submission); no salary paid without an approved run. Hourly and per-class pay use classes actually taught. | New (Payroll) |
| 21 | Test data is fictional and can never be loaded into the live system. | New (Test data) |

---

## 6. Replacing Mindbody — Migration Plan

1. **Data to bring across** (from Mindbody exports): clients and families, active pricing options with expiry dates, visit history, pricing options catalogue, products with sizes, costs and prices, stock on hand per branch, sales history (period to be decided), and staff.
2. **Clean before import:** remove test products (e.g. "Kyokushin Test"), merge duplicate clients, map each Mindbody pricing option to a program and type (membership / non-membership), apply the corrected stock counts from the September clean-start count.
3. **Trial import** into a test copy; the team checks member counts, expiries and stock against Mindbody reports (e.g. the 67 active members of 27-Sep-2026 must match).
4. **Parallel run** (suggested 2–4 weeks): both systems used side by side; weekly sales and active members reconciled between them each week.
5. **Cut-over:** freeze Mindbody entries, final import of the delta, switch front desks, payment terminals and website; Mindbody kept read-only for reference until the subscription ends.
6. **Training:** 15-minute role walkthroughs (same approach as the One Voice onboarding), plus the in-app Staff Assistant.

---

## 7. Delivery Phases

Each phase ends with a demo to the leads and sign-off before the next begins. The system goes live to replace Mindbody after Phase 3.

| Phase | Name | Contents | Outcome |
|---|---|---|---|
| **0** | Foundation | New Python/Django back end on MySQL (Section 11); data model for branches, programs, pricing, members and families, staff; login with two-factor authentication; role-based access control; tamper-evident audit log; encryption of sensitive data; **M21 test data package (first version — grows with every phase)** | A secure base to build on, with realistic Kuwait test data — **built** (see backend/README.md) |
| **1** | Members, Classes and Sales | M1 Programs & pricing, M2 Members & families, M4 Schedule, bookings & check-in, M5 POS, payments, receipts & cash-up, M6 Renewals list | Front desk can run a full day without Mindbody (in test) — **built and signed off 29-Sep-2026** |
| **2** | Operations, Reporting and Payroll | M9 Daily operations forms, M10 Weekly Sales, Weekly Branch, Active Members & dashboards, M11 Finance & Accountant, **M20 Payroll** | Weekly reports build themselves; OM verification online; first payroll run in test — **built**; demo and sign-off moved to the end of the project (Section 8.1) |
| **3** | Inventory and Migration | M8 Inventory, purchasing, vendors, counts; **online-shop provision (M19 catalogue and stock reservation)**; M18 Mindbody import; parallel run; cut-over | **Mindbody replaced** — then the first run and test (7.1). **Built in test**; demo and sign-off moved to the end of the project (O-16); going live waits on the Mindbody exports and cut-over date (O-11, O-12) |
| **4** | Training and Progression | M7 Curriculum, evaluations, test days, promotions, progress cards | Belt path tracked for every member — **built in test**; demo and sign-off moved to the end of the project (O-19) |
| **5** | Growth: Leads, Website, CMS, AI | M3 Leads & group sales, M13 Marketing, **M14 Website with CMS and events gallery** (built on the approved design template), M16 Knowledge base, SAQR chat & Staff Assistant | One funnel from ad to membership; staff edit the website themselves; AI on the homepage and inside the app |
| **6** | Members, Shop and Messaging | M15 Member & parent portal, online payments, **M19 Online shop storefront**, M17 WhatsApp/SMS notifications | Members self-serve; equipment sold online; automatic reminders |
| **7** | Management | M12 Communication & cascade, meetings, procedure library, Quarterly Business Report (RPT-01) | The whole Elite operating system in one place |

### 7.1 First Run, Test and Change Requests

This scope is the starting point, not the final list. More needs will appear once the team uses the system.

- **Test environment** with the Kuwait test data package (M21) is available from Phase 0; each phase is tested there by the people who will use it before sign-off.
- **First run:** after Mindbody is replaced (end of Phase 3), a 4-week first-run period at both branches with a short weekly feedback session per function.
- **Change requests:** anyone can submit one from inside the app (what, why, who benefits, how urgent). Systems & IT logs each request and confirms a timeline, as the Communication Procedure already requires for requests to Systems & IT.
- The leads prioritise requests monthly in the leads meeting; approved ones are added to the next phase or a follow-up release, and this scope document is updated with a new version number.

---

## 8. Decisions Needed

**Decided for Phase 1 (29 Sep 2026)**

| # | Question | Decision |
|---|---|---|
| P1-1 | Must members book to attend? | No. Members are enrolled in their regular classes and simply checked in; booking is for trials, full classes and events. Walk-ins allowed. |
| P1-2 | Check-in with an expired membership? | Allowed with a warning; the member goes onto the renewals list. |
| P1-3 | No-shows and late cancellations | Recorded for the dashboard only; no penalty. A late cancellation is under 2 hours before the class. |
| P1-4 | Freeze (Playbook item 3) | No fee to start; 1–4 weeks; once per membership; OM approves. |
| P1-5 | Elite Member tier (Playbook item 3) | Built and switched off until the eligibility rule and rate are decided. |
| P1-6 | Family / sibling discount | Set per discount in the system (test data: 10% on memberships); no fixed default. |
| P1-7 | Referral reward | A set KD credit (test data: 5.000 KD) off the referring member's next renewal. |
| P1-8 | Session packages "10×4, 12×5, 12×6" | Sessions × weeks (e.g. 10 sessions within 4 weeks). |
| P1-9 | Rooms | One per branch unless the academy adds more. |
| P1-10 | Card terminals | Amounts typed in by hand with the terminal reference; a connected terminal can come with the payment provider (decision 5). |
| P1-11 | Check-in hardware (decision 11) | Both name search and QR card are built; a scanner can be added any time. |
| P1-12 | Receipts | Printed, WhatsApp or email, chosen at each sale; WhatsApp by default (sent once a provider is chosen, decision 6). |
| P1-13 | Renewal reminders / at-risk / class-change notice / cash-up difference | 5 and 1 days before expiry; at risk after 14 days without a visit; changes with under 2 hours' notice allowed but flagged urgent; every cash-up difference recorded, above 1.000 KD needs a written reason. |

**Decided for Phase 2 (29 Sep 2026, so far)**

| # | Question | Decision |
|---|---|---|
| P2-1 | Pay types | Every pay option is available for any staff member or coach, alone or combined: monthly salary, hourly rate, rate per class taught (per program if needed), commission on sales, and allowances. |
| P2-2 | Additions and deductions | Overtime, allowances, deductions (absence, advances and repayment) and end-of-service indemnity are all included. |
| P2-3 | Payroll approval | The Accountant approves the payroll run; see P2-5 for who prepares it. |
| P2-4 | Report layouts | The Weekly Sales Report (FRM-06), Weekly Branch Report (FRM-07) and Active Members Report (EA-DOC-003) follow the copies in docs/elite-academy/. |
| P2-5 | Who prepares payroll | The system builds the draft from classes taught, sales, leave and absences; the OM checks it, adds bonuses and deductions and submits it; the Accountant approves; the CEO sees the summary. |
| P2-6 | Commission | A percentage per person and per sale category (new, renew, equipment…) on sales that person made at the desk; refunds of those sales in the same period are taken off. |
| P2-7 | Freelance coaches | Same pay options, no PIFSS, end-of-service or leave; paid in the same monthly run (not as vendors). |
| P2-8 | Pay period and pay day | Calendar month, paid on the last working day. Classes taught and sales count from the 26th of the previous month to the 25th. |
| P2-9 | Kuwait rules | Overtime +25% normal day, +50% rest day, +100% public holiday; end-of-service 15 days' pay per year for the first 5 years then a month per year, capped at 18 months, reduced on resignation; PIFSS for Kuwaiti staff; annual and sick leave. All values are settings the Accountant confirms before the first real run; a run cannot be approved until they are confirmed. |
| P2-10 | Salary advances | Approved by the OM; repaid in monthly instalments taken off the payslip automatically. |
| P2-11 | Bank file | Standard Excel/CSV transfer file until the bank is named. |
| P2-12 | Weekly Sales Report | Built from sales; "Matches Mindbody?" becomes "Matches cash-up and terminal settlement"; branch expenses entered during the week with a receipt photo; cash paid out of the drawer is taken off the cash expected at cash-up. |
| P2-13 | Weekly Branch Report | Figures fill themselves in; the Branch Admin adds the text sections; the OM verifies; references like FRM-06-BED-2026-012. |
| P2-14 | Active Members | Business rule 1, verified by attendance (last visit, visit count), snapshot every Friday for the week-over-week change. |
| P2-15 | Daily operations | Shift opening, incidents with the 24-hour CEO countdown, complaint log with the 24-hour reply, cover and handover. |
| P2-16 | Exports | Every report downloads as PDF (English or Arabic) and Excel and can be emailed on a schedule. |
| P2-17 | Scope of the income statement | Built in Phase 2 from sales, refunds, expenses and payroll; equipment cost of sales and landed costs come with inventory in Phase 3; the Quarterly Business Report stays in Phase 7. |

**Phase 3 working decisions (29 Sep 2026)** — sensible defaults so building can continue; each can be changed at the end-of-project review.

| # | Question | Working decision |
|---|---|---|
| P3-1 | Online shop | Phase 3 builds the provision only: one stock record per branch shared by the front desk and online orders, reserved when an order is placed and taken off when it is fulfilled. The storefront opens in Phase 6. |
| P3-2 | Transfers | Stock leaves the sender and reaches the receiver only when the receiver accepts (rule 9). While in transit it is held at the sender and can't be sold. A count that differs can be accepted only after confirming the sender and the OM were called; the shortfall is flagged to the OM. |
| P3-3 | Business days | Sunday–Thursday, excluding public holidays, for the 2-business-day purchase decision and the count deadline (3rd working day). |
| P3-4 | Catalogue changes | The OM (or CEO) adds products and sets costs and retail prices; branches and the coordinator request items, including items not yet in the catalogue (free text). |
| P3-5 | Landed cost | Unit price × exchange rate × (1 + customs/clearance %), plus freight shared by value. Default customs/clearance 20% and target margin 50% (from the Dhalay analysis); both editable per order. |
| P3-6 | Product cost | The latest landed cost of what was received becomes the product's cost (used for margins and, later, cost of sales). |
| P3-7 | Monthly count | Created automatically on the last working day for each branch; two people (counter and recorder); every difference recounted and given a reason code (US, UT, D, FI, EE, U); stock corrected only after the OM approves; items short two months running are flagged. |
| P3-8 | Mindbody import | From Mindbody's standard exports (clients, relationships, pricing option expirations, visits, sales, inventory on hand). Every import is first run as a dry run with a report; nothing changes until it is applied. Re-running is safe (records are matched by their Mindbody ID), so the final delta at cut-over uses the same tool. |
| P3-9 | Cleaning | Test products are skipped; possible duplicate clients are listed for a person to merge; each Mindbody pricing option is mapped to a system pricing option (or skipped) before memberships are imported; the stock baseline is confirmed with the first monthly count. |
| P3-10 | Staff | Staff accounts are set up in the system by Systems & IT (not imported), since roles and access must be assigned by a person. |

**Phase 4 working decisions (29 Sep 2026)** — sensible defaults so building can continue; each can be changed at the end-of-project review.

| # | Topic | Working decision |
|---|---|---|
| P4-1 | Belt systems | The Kajukenbo scalable curriculum is loaded from the Master Curriculum workbook: one belt (Kajukenbo rank + Kickboxing level), one stripe (Jiu-Jitsu / BJJ level), seminar points for Self-Defence & Traditional. The "suggested additions" (orange) are not loaded; the Training Lead adds them in the curriculum builder if wanted. Kyokushin, Shin-Kyokushin and Taekwondo get their own belt lists, without skills until the Training Lead fills them in. A member follows an art through the programs they are enrolled in or attend. |
| P4-2 | Reading the workbook | Skills listed under a belt are what the student works on while wearing it and are tested to earn the next belt. Seminar numbers are the total seminars attended needed to be awarded that belt. |
| P4-3 | Eligibility for the next belt | Minimum classes since the last promotion, minimum weeks at the current belt, seminar total reached, and at least 2 evaluations since the last promotion with the latest marked "ready for test". Defaults per belt (editable): classes 24, 24, 36, 36, 48, 60, 72 and weeks 12, 12, 16, 16, 24, 36, 52 for Yellow to Black. |
| P4-4 | Evaluations | Due 4 weeks after the last one (or the last promotion), overdue after 6 weeks, with reminders to the member's instructors. Each skill scored 1 Not yet, 2 Developing, 3 Competent, 4 Strong; a skill scored 3 or 4 is ticked off on the progress card. |
| P4-5 | Who evaluates | The member's instructors (their regular class, or a class they taught the member in the last 90 days) and the Training and Track Leads. Seminar points come from check-ins at seminar sessions; earlier seminars are added by a Training or Track Lead with a note. |
| P4-6 | Test days | A Training or Track Lead creates the test day and adds eligible students (anyone not eligible only with a written reason). Examiners record each component — Kickboxing, Jiu-Jitsu, seminar points check (automatic), Self-Defence demo; other arts have one practical component. A pass needs every component passed; the promotion is confirmed by a Training or Track Lead. |
| P4-7 | Belts | A promotion puts the belt on the branch's hand-over list; the front desk issues it from branch stock as a 0 KD free issue ("Grading belt"), so stock reduces. The guardian (or adult member) is told by WhatsApp. The Google review request comes with Phase 5 (M13). |
| P4-8 | Existing students | Their current belt is set once by a Training or Track Lead ("placement") with a note, and kept in the belt history. |
| P4-9 | Monthly progress note | Drafted automatically on the 1st of the month for each child who trained the month before (skills ticked, what's next); the instructor edits it and sends it to the guardian. |
| P4-10 | Tournament eligibility | Shown from the belt: striking level = belt; BJJ equivalent from the stripe; Kajukenbo rank. |

**Carried from Elite documents**
1. Receiving owner for group-sales handoffs (Playbook item 1).
2. Elite Member tier: eligibility rules and rate (Playbook item 3).
3. Freeze fee: amount and approval process (Playbook item 3).
4. Systems & IT reporting cadence to the CEO (Communication open item 2).

*Resolved by this system:* where consent forms are stored and who audits them (M13), where the campaign tracker lives (M13), how both leads see Roaa's instructions (M12), and the lead-owner tie-breaker (M3).

**New decisions for the system**
5. **Online payment gateway** for KNET and cards (e.g. MyFatoorah, Tap, UPayments) and whether front-desk card terminals connect to the system or are entered manually.
6. **WhatsApp Business API provider** for SAQR on WhatsApp and member notifications; SMS provider for one-time login codes.
7. **What happens to the current SAQR provider** once the new SAQR chat is live (move WhatsApp to the new assistant, or keep both for a period).
8. **Accounting software** the accountant uses (export format or direct integration).
9. **How much sales history** to import from Mindbody (e.g. from 2019, or last 2 years).
10. **Hosting and domain:** where the system is hosted, and whether elitemaacademy.com moves to the new website.
11. **Check-in hardware** at each front desk (tablet with QR scanner, or staff search only).
12. **Branding:** logo files, colours and fonts for the system, website and receipts.
13. **Knowledge base owners** for public and internal articles.
14. **Online shop fulfilment:** pickup only, or also home delivery (courier and delivery fees by area); return and exchange policy.
15. **Payroll set-up:** list of directly hired staff vs freelance coaches, salary structures and hourly rates, pay day, salary-transfer bank, PIFSS registration details; the Accountant confirms end-of-service and leave rules.
16. **Website CMS:** who besides the Marketing Lead may approve publishing; watermark on gallery photos (yes/no).
17. **Website template:** choose one of the Claude Design options built from the design brief (EA-SYS-DESIGN-01) and supply the logo files.

---

### 8.1 Open items — closed one by one at the end of the project

| # | Item | From |
|---|---|---|
| O-1 | Phase 2 demo and sign-off (payroll, reports, finance, operations) | Phase 2 |
| O-2 | Accountant confirms the payroll rules: PIFSS rates and cap, overtime, end-of-service, leave | P2-9 |
| O-3 | Salary-transfer bank and its file format | P2-11, decision 15 |
| O-4 | Remove real member and staff data from the code repository (Active Members report, staff contact list) | Security |
| O-5 | Hosting and domain | Decision 10 |
| O-6 | Payment gateway (KNET / cards, online) and whether card terminals connect | Decision 5 |
| O-7 | WhatsApp Business and SMS provider (receipts, reminders, payslips, codes) | Decision 6 |
| O-8 | Email sending service (receipts, emailed reports) | New |
| O-9 | Accounting software and export format | Decision 8 |
| O-10 | How much sales history to import from Mindbody | Decision 9 |
| O-11 | The Mindbody exports themselves (both branches) and the pricing-option mapping | P3-8, P3-9 |
| O-12 | Parallel-run length and cut-over date | Section 6 |
| O-13 | Elite Member tier rule and rate; freeze fee | Decisions 2, 3 |
| O-14 | Payroll set-up per person: directly hired vs freelance, rates, PIFSS registration | Decision 15 |
| O-15 | Remaining earlier decisions: 1, 4, 7, 11–14, 16–17 | Section 8 |
| O-16 | Phase 3 demo and sign-off (inventory, purchasing, counts, online stock, Mindbody import, parallel run, cut-over) | Phase 3 |
| O-17 | Stock settings to confirm: customs/clearance % and target margin (P3-5), reorder and maximum levels per item, which items are sold online | P3-5, P3-1 |
| O-18 | Training Lead confirms the Phase 4 numbers (classes, weeks, seminar totals, evaluation cadence and scores), the suggested additions, and the belt lists for Kyokushin, Shin-Kyokushin and Taekwondo | P4-1 to P4-4 |
| O-19 | Phase 4 demo and sign-off (curriculum, progress cards, evaluations, test days, promotions, progress notes) | Phase 4 |

## 9. Out of Scope (for now)

- A full double-entry accounting ledger (the system exports to the accountant's tool).
- Native iPhone/Android apps (the portal and shop are a mobile-friendly web app that can be added to the home screen).
- Items added after the first run are handled through change requests (Section 7.1).

---

## 10. What Carries Over from the Current Codebase

The starting code is a multi-centre clinic management system (Node.js, PostgreSQL). Because the system is now built in Python with MySQL (Section 11), the clinic code is kept **as a reference only** — for its screens, workflows and reports — and is not extended. Its concepts map to Elite as follows:

| Current app | Becomes |
|---|---|
| Centres (isolated data) | Branches |
| Departments | Programs / disciplines |
| Doctors (+ doctor login and dashboard) | Instructors (+ instructor view) |
| Patients | Members and families |
| Clinic weekly assignments | Class timetable and instructor assignments |
| Appointments + reception desk + live arrival alerts | Bookings, check-in and live check-in alerts |
| Leaves and permissions | Instructor leave and class cover |
| Call-centre exam booking slots | Trial booking slots |
| Procedure logs and statistics | Evaluations and progress statistics |
| Doctor of the Month | Instructor / Student of the Month |
| Department statistics and monitoring dashboards | Branch and program dashboards |

Not carried over: Replit login, dental procedure fields, and browser-side data isolation. The clinic code's security gaps (62 API routes without login checks) do not apply to the new back end, where every endpoint is closed unless it declares a permission.

---

## 11. Technology and Non-Functional Requirements

### 11.1 Technology

| Part | Choice |
|---|---|
| Back end | Python 3.11+, Django 5.2 LTS, Django REST Framework |
| Database | MySQL 8 (utf8mb4 for Arabic) |
| Sessions, cache, background jobs | Redis; Celery for scheduled jobs (reminders, reports, escalation timers, audit sealing) |
| Website CMS and gallery (M14) | Wagtail (Django-based CMS) |
| Front end | Built from the approved Claude Design template (EA-SYS-DESIGN-01); the website renders from the CMS for search engines; the staff system and member portal use the same design system |
| AI (M16) | Claude, called only from the back end, with the user's permissions applied |
| Quality gates | Automated tests on MySQL, lint, code security scan (Bandit), dependency vulnerability scan (pip-audit) on every change |

### 11.2 Many users at the same time

Clients, parents, coaches and staff at both branches use the system simultaneously. The system must:
- keep every save all-or-nothing (one database transaction per request);
- never lose an edit silently — when two people edit the same record, the second is told the record changed and asked to reload (optimistic locking);
- keep shared counters exact under load (row locks for stock and class places);
- scale by adding application servers (sessions in Redis, no per-server state);
- protect service for everyone with per-user and per-address rate limits.

Acceptance: load test with at least 150 simultaneous users mixing staff, coaches and parents — no server errors, no cross-branch data exposure, all edit collisions rejected safely. Phase 0 result: passed (150 users, 3,283 requests, 0 errors, 0 leaks).

### 11.3 Security — ISO/IEC 27001:2022 alignment

The system implements the technical controls of ISO/IEC 27001:2022 Annex A and produces the evidence an auditor needs; certification itself also requires Elite's own management system (policies, risk assessment, suppliers, training). The control-by-control mapping, with tests, is in EA-SYS-SEC-01. Key requirements:
- two-factor login for privileged roles; account lockout; session timeouts;
- encryption of Civil IDs and medical information at rest, TLS in transit;
- masking of sensitive data for roles that don't need it;
- append-only, tamper-evident audit log of every change, login and denied access;
- leaver process that removes all access immediately;
- separated development, test and production environments; fictional test data only.

### 11.4 Role-based access control

- Access comes only from roles (13 default roles, 38 permissions — EA-SYS-SEC-02 RBAC Matrix); anything not granted is refused.
- Roles can be limited to one branch; data from other branches is never sent.
- Sensitive fields need their own permission (full Civil ID, medical notes).
- No one can change their own access or hand out powers they don't hold; every grant records who, why, from when and until when.
- Parents and adult members see only their own family through the portal.

---

## Approval

| | Prepared By | Reviewed By | Approved By |
|---|---|---|---|
| Designation | Systems & IT Lead | Operations Lead (COO) | Chief Executive Officer |
| Name | | | |
| Signature | | | |
| Date | | | |
