// Barrel file — re-exports every domain schema module so existing imports of
// "@shared/schema" keep working unchanged. See replit.md for the domain
// isolation rules that these tables must respect.
export * from "./auth";
export * from "./centers";
export * from "./departments";
export * from "./doctors";
export * from "./clinics";
export * from "./scheduling";
export * from "./settings";
export * from "./patients";
export * from "./appointments";
export * from "./doctor-of-month";
export * from "./procedures";
export * from "./overtime";
export * from "./exam-schedule";
export * from "./relations";
