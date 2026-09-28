# Elite Academy System — Scope of Work

| Field | Detail |
|---|---|
| Document Number | EA-SYS-SCOPE-01 |
| Title | Elite Academy System — Scope of Work |
| Version | 0.1 (Draft for review) |
| Date | 28-Sep-2026 |
| Document Owner | Systems & IT Lead |
| Reviewed By | Operations Lead (COO); Training Lead; Marketing Lead |
| Approved By | Chief Executive Officer |
| Related Documents | EA-OPS-PROC-01 Operations Procedure; EA-INV-PROC-01 Inventory Management Procedure; EA-COMM-PROC-01 Communication Procedure; EA-COMM-PLAY-01 How We Work Together; EA-COMM-REF-01 Org Chart; Customer Management Procedure & One Voice Guide; Marketing Funnel by Branch; Kajukenbo Master Curriculum; Active Members Report (EA-DOC-003) |

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
| **Marketing Lead** | Maryam | Campaigns, funnel, group sales, knowledge base (voice & content), website content | Both branches, marketing data (no payments) |
| **Marketing Implementation** | Ayaa | Campaign tracker, consented media library, website content | As Marketing Lead, no approvals |
| **Systems & IT Lead** | Saud | Users, roles, settings, integrations, AI configuration, audit log, data imports | System-wide admin |
| **Branch Admin** | Verna (Promenade), Tareq (Bedaya) | Front desk: check-in, trials, registration, sales, renewals follow-up, class changes, daily/weekly forms, stock | Own branch (plus "both branches" duties where the playbook assigns them) |
| **Operations Support / Coach** | Roaa | Front desk duties at either branch + instructor duties; handles AI handoffs | Both branches; instructions visible to both her leads |
| **Purchasing / Receiving Coordinator** | (Promenade) | Place approved orders, receive deliveries, discrepancy reports | Inventory, both branches |
| **Accountant** | (new user) | Cash-up and settlement reconciliation, expenses, income statements, exports | Financial data, both branches, read-only on members |
| **Member / Parent** | Clients | Portal: schedule, bookings, payments, renewals, progress, consent, family | Own family only |
| **Public visitor** | Anyone | Website, schedule, prices, trial booking, SAQR chat | Public info only |

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

### M14. Public Website and Online Booking
*Replaces: the current website admin panel.*

- Branch pages with their own positioning ("Complete Fighter Program" at Promenade; "Choose Your Discipline" and the ladies' class at Bedaya).
- Programs, schedule and prices shown **live from the system** (no separate website updates).
- Instructor profiles (rank, years training, competition background).
- **Book a trial** with name and phone only → becomes a lead with an owner.
- **SAQR chat window** on every page (M16).
- Arabic and English, mobile first.

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
| **0** | Foundation | Fix security gaps in the current code; remove Replit dependencies; new data model (branches, programs, members, staff, roles); login and permissions; Arabic/English layout; audit log | A secure base to build on |
| **1** | Members, Classes and Sales | M1 Programs & pricing, M2 Members & families, M4 Schedule, bookings & check-in, M5 POS, payments, receipts & cash-up, M6 Renewals list | Front desk can run a full day without Mindbody (in test) |
| **2** | Operations and Reporting | M9 Daily operations forms, M10 Weekly Sales, Weekly Branch, Active Members & dashboards, M11 Finance & Accountant | Weekly reports build themselves; OM verification online |
| **3** | Inventory and Migration | M8 Inventory, purchasing, vendors, counts; M18 Mindbody import; parallel run; cut-over | **Mindbody replaced** |
| **4** | Training and Progression | M7 Curriculum, evaluations, test days, promotions, progress cards | Belt path tracked for every member |
| **5** | Growth: Leads, Website, AI | M3 Leads & group sales, M13 Marketing, M14 Website, M16 Knowledge base, SAQR chat & Staff Assistant | One funnel from ad to membership; AI on the homepage and inside the app |
| **6** | Members and Messaging | M15 Member & parent portal, online payments, M17 WhatsApp/SMS notifications | Members self-serve; automatic reminders |
| **7** | Management | M12 Communication & cascade, meetings, procedure library, Quarterly Business Report (RPT-01) | The whole Elite operating system in one place |

---

## 8. Decisions Needed

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

---

## 9. Out of Scope (for now)

- Payroll processing (the system reports instructor hours; salaries are paid outside it).
- A full double-entry accounting ledger (the system exports to the accountant's tool).
- Native iPhone/Android apps (the portal is a mobile-friendly web app that can be added to the home screen).
- Retail e-commerce shop (online sale of gear) — can be added after Phase 6.

---

## 10. What Carries Over from the Current Codebase

The starting code is a multi-centre clinic management system with the same shape Elite needs:

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

Removed: Replit login, dental procedure fields, browser-side data isolation (moved to the server). The 62 API routes that currently lack login checks are fixed in Phase 0.

---

## Approval

| | Prepared By | Reviewed By | Approved By |
|---|---|---|---|
| Designation | Systems & IT Lead | Operations Lead (COO) | Chief Executive Officer |
| Name | | | |
| Signature | | | |
| Date | | | |
