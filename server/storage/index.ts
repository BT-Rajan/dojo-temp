// Composes the domain repository modules into the single `storage` object
// that routes.ts calls (storage.getDoctors(), storage.createAppointment(),
// etc.) — same external surface as the old monolithic DatabaseStorage class,
// just assembled from per-domain files instead of one 2,800-line file.
//
// Cross-domain calls (e.g. procedures needing a doctor lookup) are plain
// imports between these modules rather than `this.` dispatch — see each
// module's own imports for its dependencies.
import * as users from "./users";
import * as centers from "./centers";
import * as departments from "./departments";
import * as settings from "./settings";
import * as controlCenter from "./control-center";
import * as doctors from "./doctors";
import * as clinics from "./clinics";
import * as scheduling from "./scheduling";
import * as dashboard from "./dashboard";
import * as patients from "./patients";
import * as appointments from "./appointments";
import * as doctorOfMonth from "./doctor-of-month";
import * as procedures from "./procedures";
import * as overtime from "./overtime";
import * as examSchedule from "./exam-schedule";

export const storage = {
  ...users,
  ...centers,
  ...departments,
  ...settings,
  ...controlCenter,
  ...doctors,
  ...clinics,
  ...scheduling,
  ...dashboard,
  ...patients,
  ...appointments,
  ...doctorOfMonth,
  ...procedures,
  ...overtime,
  ...examSchedule,
};
