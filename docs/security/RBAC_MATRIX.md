# RBAC Matrix — Default Roles and Permissions

Document: EA-SYS-SEC-02 · Generated from `backend/apps/rbac/catalog.py` (the single source of truth) by `backend/scripts/build_rbac_matrix.py`. Regenerate after any change.

✓ = granted. Branch-scoped roles (e.g. Branch Admin, Instructor) apply the permission only in their assigned branch. ★ = privileged role (two-factor login required in production).

| Role code | Role | Privileged | Description |
|---|---|---|---|
| `ceo` (CEO) | Chief Executive Officer / الرئيس التنفيذي | ★ | Direction and alignment; sees everything. |
| `operations_manager` (OM) | Operations Manager (COO) / مدير العمليات | ★ | Runs operations across both branches. |
| `training_lead` (Train) | Training Lead / مسؤول التدريب |  | Programs, curriculum and instructors. |
| `track_lead` (Track) | Track Lead / قائد المسار |  | Leads the grappling or striking track. |
| `instructor` (Coach) | Instructor / مدرب |  | Teaches classes; sees their students. |
| `marketing_lead` (Mkt) | Marketing Lead / مسؤولة التسويق |  | Campaigns, website and brand. |
| `marketing_staff` (MktI) | Marketing Implementation / تنفيذ التسويق |  | Implements campaigns and content. |
| `it_admin` (IT) | Systems & IT Lead / مسؤول الأنظمة وتقنية المعلومات | ★ | Users, roles and system settings. |
| `branch_admin` (BrAdm) | Branch Admin / إداري الفرع |  | Front desk and daily branch operations. |
| `operations_support` (OpsSp) | Operations Support / دعم العمليات |  | Front desk support at either branch. |
| `purchasing_coordinator` (Purch) | Purchasing / Receiving Coordinator / منسق المشتريات |  | Orders and deliveries. |
| `accountant` (Acct) | Accountant / المحاسب | ★ | Finance, reconciliation and payroll approval. |
| `guardian` (Parent) | Parent / Member / ولي الأمر / العضو |  | Portal access to own family only. |

| Permission | Meaning | CEO | OM | Train | Track | Coach | Mkt | MktI | IT | BrAdm | OpsSp | Purch | Acct | Parent |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `branches.view` | View branches | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| `branches.manage` | Create and edit branches | ✓ |  |  |  |  |  |  | ✓ |  |  |  |  |  |
| `programs.view` | View disciplines, programs and pricing options | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| `programs.manage` | Create and edit programs | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |
| `pricing.manage` | Create and edit pricing options (price changes need approval) | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `pricing.approve` | Approve price changes | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `members.view` | View members and families | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ | ✓ |  |  |  |
| `members.create` | Register members | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `members.update` | Edit member details | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `members.deactivate` | Deactivate members | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `members.view_sensitive` | See full Civil IDs | ✓ | ✓ |  |  |  |  |  |  | ✓ |  |  |  |  |
| `members.view_medical` | See medical notes and allergies | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ | ✓ |  |  |  |
| `members.manage_consent` | Record media consent | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `staff.view` | View staff directory | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ | ✓ |  |  | ✓ |  |
| `staff.manage` | Create and edit staff records | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `rbac.view` | View roles and assignments | ✓ | ✓ |  |  |  |  |  | ✓ |  |  |  |  |  |
| `rbac.assign` | Assign and end roles | ✓ | ✓ |  |  |  |  |  | ✓ |  |  |  |  |  |
| `rbac.manage_roles` | Change what roles can do | ✓ |  |  |  |  |  |  | ✓ |  |  |  |  |  |
| `audit.view` | Read the audit log | ✓ | ✓ |  |  |  |  |  | ✓ |  |  |  |  |  |
| `system.admin` | Technical administration |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |
| `classes.view` | See the timetable, sessions and class lists | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ | ✓ |  |  |  |
| `classes.manage` | Edit the weekly timetable, rooms and one-off sessions | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |
| `classes.book` | Book members and trials into classes | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `classes.checkin` | Check members in and take attendance | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ | ✓ |  |  |  |
| `classes.change_request` | Request a class cancellation, time change or substitute coach | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ | ✓ |  |  |  |
| `classes.change_approve` | Approve class changes (members are notified) | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |
| `sales.view` | See sales, receipts and memberships | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  | ✓ |  |
| `sales.request` | Log freeze, refund and cancellation requests | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `sales.cashup` | Prepare and submit the end-of-day cash-up | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `renewals.follow_up` | Work the renewals follow-up list | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `sales.sell` | Sell at the front desk | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `sales.approve_refund` | Approve freezes, refunds and cancellations | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `reports.branch` | Branch reports | ✓ | ✓ | ✓ |  |  | ✓ |  |  | ✓ | ✓ |  |  |  |
| `reports.all` | All-branch and quarterly reports | ✓ | ✓ |  |  |  |  |  |  |  |  |  | ✓ |  |
| `reports.verify` | Verify weekly reports | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `inventory.manage` | Stock counts, transfers and receiving | ✓ | ✓ |  |  |  |  |  |  | ✓ |  | ✓ |  |  |
| `inventory.approve` | Approve purchase requests and stock corrections | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `training.manage` | Curriculum, evaluations and promotions | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  |  |  |
| `training.teach` | Take attendance and evaluate own classes | ✓ |  | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |
| `marketing.manage` | Campaigns, leads and media library | ✓ |  |  |  |  | ✓ | ✓ |  |  |  |  |  |  |
| `cms.edit` | Draft website content | ✓ |  |  |  |  | ✓ | ✓ |  |  |  |  |  |  |
| `cms.publish` | Publish website content | ✓ |  |  |  |  | ✓ |  |  |  |  |  |  |  |
| `leads.manage` | Follow up website trial requests and contact messages | ✓ | ✓ |  |  |  | ✓ | ✓ |  | ✓ | ✓ |  |  |  |
| `finance.manage` | Reconciliation, income statements, vendor invoices and exports | ✓ | ✓ |  |  |  |  |  |  |  |  |  | ✓ |  |
| `finance.expense` | Record branch expenses with a receipt photo | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `finance.expense_approve` | Approve branch expenses | ✓ | ✓ |  |  |  |  |  |  |  |  |  | ✓ |  |
| `payroll.prepare` | Set up staff pay and prepare the monthly payroll run |  | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `payroll.view` | See payroll runs, payslips and summaries | ✓ | ✓ |  |  |  |  |  |  |  |  |  | ✓ |  |
| `payroll.approve` | Approve the monthly payroll run |  |  |  |  |  |  |  |  |  |  |  | ✓ |  |
| `payroll.self` | See own payslips; request leave and salary advances | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| `leave.approve` | Approve staff leave | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |
| `incidents.escalate` | Receive safety escalations | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |
| `ops.shift` | Complete the shift opening checklist | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| `ops.incident` | Report incidents | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ | ✓ |  |  |  |
| `ops.complaint` | Log and handle complaints | ✓ | ✓ |  |  |  | ✓ |  |  | ✓ | ✓ |  |  |  |
| `ops.manage` | Follow up incidents and complaints, name cover and handovers | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| `portal.own_family` | See and manage own family in the portal |  |  |  |  |  |  |  |  |  |  |  |  | ✓ |

## Rules that apply on top of the matrix

1. **Deny by default.** An API endpoint that does not declare a permission is closed to everyone.
2. **Branch scope.** A role assigned to one branch grants its permissions for that branch only; lists silently exclude other branches, and records from other branches return *not found*.
3. **Need-to-know fields.** Full Civil IDs need `members.view_sensitive`; medical notes and allergies need `members.view_medical`. Otherwise Civil IDs are masked (`********1234`) and medical fields are omitted.
4. **No privilege escalation.** A user may only grant a role whose permissions they already hold (unless they hold `rbac.manage_roles`), only in branches where they hold `rbac.assign`, and never to themselves.
5. **Time-bound access.** Every assignment has a start date and an end date (first day without access). Ending an assignment or deactivating a user signs them out of every device immediately.
6. **Superuser is not a business role.** Django's superuser flag opens only the technical admin site; it grants no access to member, finance or payroll data through the application.
7. **Portal isolation.** Parents and adult members see only records reached through their own guardian/member profile, never by an id sent from the browser.
