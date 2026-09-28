import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { format, subMonths, startOfMonth, endOfMonth } from "date-fns";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft, Users, TrendingUp, TrendingDown, BarChart3, Activity,
  Stethoscope, FileText, Filter, Download, ThumbsUp, ThumbsDown,
  ChevronUp, ChevronDown, Minus
} from "lucide-react";

interface Doctor {
  id: number;
  name: string;
  title: string;
  departmentId: number;
}

interface Department {
  id: number;
  name: string;
}

interface ProcedureStats {
  perDoctor: Array<{
    doctor: Doctor;
    treatedPatients: number;
    completedAppointments: number;
    procedureTotals: Record<string, number>;
  }>;
  departmentTotals: {
    treatedPatients: number;
    completedAppointments: number;
    procedureTotals: Record<string, number>;
  };
  dailyBreakdown: Array<{
    date: string;
    treatedPatients: number;
    totalProcedures: number;
  }>;
}

const procedureLabels: Record<string, string> = {
  alginatePreparation: "Alginate Preparation",
  crownPreparation: "Crown Preparation",
  bridgePreparation: "Bridge Preparation",
  finalImpression: "Final Impression",
  tempCementation: "Temp. Cementation",
  cementAccBb: "Cement ACC & BB",
  cementPorcelainCb: "Cement Porcelain C&B",
  metalCrownCb: "Metal Crown C&B",
  porcelainCb: "Porcelain C&B",
  postPreparation: "Post Preparation",
  postCanal: "Post Canal",
  compositeFilling: "Composite Filling",
  amalgamFilling: "Amalgam Filling",
  removableProstho: "Removable Prostho.",
  removableProsthoRepair: "Removable Prostho. Repair",
  cbRemovalPostCore: "C&B Removal / Post & Core",
  orthoAppliances: "Ortho Appliances",
  buckleAppointment: "Buckle Appointment",
  implantUnits: "Implant Units",
  tryIn: "Try-In",
  miscellaneous: "Miscellaneous",
  examination: "Examination",
};

const procedureKeys = Object.keys(procedureLabels);

export default function DepartmentStatistics() {
  const [, setLocation] = useLocation();
  const [selectedDepartment, setSelectedDepartment] = useState<number | null>(null);
  const [selectedDoctorFilter, setSelectedDoctorFilter] = useState<string>("all");
  const [startDate, setStartDate] = useState(format(startOfMonth(subMonths(new Date(), 0)), "yyyy-MM-dd"));
  const [endDate, setEndDate] = useState(format(endOfMonth(new Date()), "yyyy-MM-dd"));
  const [reportView, setReportView] = useState<"overview" | "procedures" | "doctors" | "strengths">("overview");

  const { data: user } = useQuery<any>({ queryKey: ["/api/auth/user"] });

  const centerId = localStorage.getItem("selectedCenterId") || "";

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["/api/user/departments", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/user/departments?centerId=${centerId}` : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch departments");
      return res.json();
    },
    enabled: !!user,
  });

  useEffect(() => {
    if (departments.length > 0 && !selectedDepartment) {
      setSelectedDepartment(departments[0].id);
    }
  }, [departments, selectedDepartment]);

  const statsQueryKey = useMemo(() => {
    if (!selectedDepartment) return null;
    const doctorParam = selectedDoctorFilter !== "all" ? `&doctorId=${selectedDoctorFilter}` : "";
    return `/api/department/${selectedDepartment}/procedure-stats?startDate=${startDate}&endDate=${endDate}${doctorParam}`;
  }, [selectedDepartment, startDate, endDate, selectedDoctorFilter]);

  const { data: stats, isLoading: statsLoading } = useQuery<ProcedureStats>({
    queryKey: [statsQueryKey],
    enabled: !!statsQueryKey,
  });

  const { data: departmentDoctors = [] } = useQuery<Doctor[]>({
    queryKey: [`/api/doctors?departmentId=${selectedDepartment}`],
    enabled: !!selectedDepartment,
  });

  const totalProcedures = useMemo(() => {
    if (!stats) return 0;
    return Object.values(stats.departmentTotals.procedureTotals).reduce((sum, v) => sum + v, 0);
  }, [stats]);

  const sortedProcedures = useMemo(() => {
    if (!stats) return [];
    return procedureKeys
      .map(key => ({ key, label: procedureLabels[key], count: stats.departmentTotals.procedureTotals[key] || 0 }))
      .sort((a, b) => b.count - a.count);
  }, [stats]);

  const strengths = useMemo(() => sortedProcedures.filter(p => p.count > 0).slice(0, 5), [sortedProcedures]);
  const weaknesses = useMemo(() => {
    const withActivity = sortedProcedures.filter(p => p.count >= 0);
    return withActivity.slice(-5).reverse().filter(p => {
      const maxCount = sortedProcedures[0]?.count || 0;
      return maxCount > 0 && p.count < maxCount * 0.3;
    });
  }, [sortedProcedures]);

  const avgPatientsPerDoctor = useMemo(() => {
    if (!stats || stats.perDoctor.length === 0) return 0;
    const activeDoctors = stats.perDoctor.filter(d => d.completedAppointments > 0).length;
    return activeDoctors > 0 ? Math.round(stats.departmentTotals.treatedPatients / activeDoctors) : 0;
  }, [stats]);

  const setQuickDateRange = (range: string) => {
    const now = new Date();
    switch (range) {
      case "this-month":
        setStartDate(format(startOfMonth(now), "yyyy-MM-dd"));
        setEndDate(format(endOfMonth(now), "yyyy-MM-dd"));
        break;
      case "last-month":
        setStartDate(format(startOfMonth(subMonths(now, 1)), "yyyy-MM-dd"));
        setEndDate(format(endOfMonth(subMonths(now, 1)), "yyyy-MM-dd"));
        break;
      case "last-3-months":
        setStartDate(format(startOfMonth(subMonths(now, 2)), "yyyy-MM-dd"));
        setEndDate(format(endOfMonth(now), "yyyy-MM-dd"));
        break;
      case "last-6-months":
        setStartDate(format(startOfMonth(subMonths(now, 5)), "yyyy-MM-dd"));
        setEndDate(format(endOfMonth(now), "yyyy-MM-dd"));
        break;
    }
  };

  const handleExportCSV = () => {
    if (!stats) return;
    const headers = ["Doctor", "Treated Patients", "Completed Appointments", ...procedureKeys.map(k => procedureLabels[k])];
    const rows = stats.perDoctor.map(d => [
      d.doctor.name,
      d.treatedPatients,
      d.completedAppointments,
      ...procedureKeys.map(k => d.procedureTotals[k] || 0)
    ]);
    rows.push([
      "DEPARTMENT TOTAL",
      stats.departmentTotals.treatedPatients,
      stats.departmentTotals.completedAppointments,
      ...procedureKeys.map(k => stats.departmentTotals.procedureTotals[k] || 0)
    ]);
    const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `department-stats-${startDate}-to-${endDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getBarWidth = (value: number, max: number) => {
    if (max === 0) return 0;
    return Math.max(2, (value / max) * 100);
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
              <BarChart3 className="h-8 w-8 text-blue-600" />
              Department Statistics
            </h1>
            <p className="text-gray-600 dark:text-gray-300 mt-1">
              Procedure analysis, doctor performance, and department insights
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={handleExportCSV} disabled={!stats}>
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
            <Button variant="outline" onClick={() => setLocation("/")}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Home
            </Button>
          </div>
        </div>

        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
              <div>
                <Label className="text-sm font-medium mb-1 block">Department</Label>
                <Select
                  value={selectedDepartment?.toString() || ""}
                  onValueChange={(v) => { setSelectedDepartment(parseInt(v)); setSelectedDoctorFilter("all"); }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map(d => (
                      <SelectItem key={d.id} value={d.id.toString()}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-sm font-medium mb-1 block">Doctor</Label>
                <Select value={selectedDoctorFilter} onValueChange={setSelectedDoctorFilter}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Doctors</SelectItem>
                    {departmentDoctors.map(d => (
                      <SelectItem key={d.id} value={d.id.toString()}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-sm font-medium mb-1 block">From</Label>
                <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
              </div>
              <div>
                <Label className="text-sm font-medium mb-1 block">To</Label>
                <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
              </div>

              <div>
                <Label className="text-sm font-medium mb-1 block">Quick Range</Label>
                <Select onValueChange={setQuickDateRange}>
                  <SelectTrigger>
                    <Filter className="h-4 w-4 mr-2" />
                    <SelectValue placeholder="Select range" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="this-month">This Month</SelectItem>
                    <SelectItem value="last-month">Last Month</SelectItem>
                    <SelectItem value="last-3-months">Last 3 Months</SelectItem>
                    <SelectItem value="last-6-months">Last 6 Months</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {statsLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
          </div>
        ) : !stats ? (
          <Card>
            <CardContent className="py-12 text-center text-gray-500">
              Select a department and date range to view statistics
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Patients Treated</CardTitle>
                  <Users className="h-4 w-4 text-blue-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">{stats.departmentTotals.treatedPatients}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Avg {avgPatientsPerDoctor} per doctor
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Completed Visits</CardTitle>
                  <Activity className="h-4 w-4 text-green-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">{stats.departmentTotals.completedAppointments}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Appointment sessions logged
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Total Procedures</CardTitle>
                  <Stethoscope className="h-4 w-4 text-purple-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">{totalProcedures}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Across {sortedProcedures.filter(p => p.count > 0).length} procedure types
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Active Doctors</CardTitle>
                  <FileText className="h-4 w-4 text-orange-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">
                    {stats.perDoctor.filter(d => d.completedAppointments > 0).length}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Out of {stats.perDoctor.length} in department
                  </p>
                </CardContent>
              </Card>
            </div>

            <div className="flex gap-2 mb-6 flex-wrap">
              {(["overview", "procedures", "doctors", "strengths"] as const).map(view => (
                <Button
                  key={view}
                  variant={reportView === view ? "default" : "outline"}
                  size="sm"
                  onClick={() => setReportView(view)}
                >
                  {view === "overview" && <BarChart3 className="h-4 w-4 mr-2" />}
                  {view === "procedures" && <Stethoscope className="h-4 w-4 mr-2" />}
                  {view === "doctors" && <Users className="h-4 w-4 mr-2" />}
                  {view === "strengths" && <TrendingUp className="h-4 w-4 mr-2" />}
                  {view === "overview" ? "Overview" : view === "procedures" ? "By Procedure" : view === "doctors" ? "By Doctor" : "Strengths & Weaknesses"}
                </Button>
              ))}
            </div>

            {reportView === "overview" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Top Procedures</CardTitle>
                    <CardDescription>Most frequently performed procedures</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {sortedProcedures.filter(p => p.count > 0).length === 0 ? (
                      <p className="text-gray-500 text-center py-8">No procedure data recorded for this period</p>
                    ) : (
                      <div className="space-y-3">
                        {sortedProcedures.filter(p => p.count > 0).slice(0, 10).map((proc, i) => (
                          <div key={proc.key} className="flex items-center gap-3">
                            <span className="text-sm font-medium text-gray-500 w-6">{i + 1}</span>
                            <div className="flex-1">
                              <div className="flex justify-between items-center mb-1">
                                <span className="text-sm font-medium">{proc.label}</span>
                                <span className="text-sm font-bold">{proc.count}</span>
                              </div>
                              <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                                <div
                                  className="bg-blue-600 h-2 rounded-full transition-all"
                                  style={{ width: `${getBarWidth(proc.count, sortedProcedures[0]?.count || 1)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Daily Activity</CardTitle>
                    <CardDescription>Patients treated and procedures per day</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {stats.dailyBreakdown.length === 0 ? (
                      <p className="text-gray-500 text-center py-8">No daily data for this period</p>
                    ) : (
                      <div className="space-y-2 max-h-[400px] overflow-y-auto">
                        {stats.dailyBreakdown.map(day => {
                          const maxPatients = Math.max(...stats.dailyBreakdown.map(d => d.treatedPatients), 1);
                          return (
                            <div key={day.date} className="flex items-center gap-3 py-1">
                              <span className="text-xs text-gray-500 w-20 shrink-0">
                                {format(new Date(day.date + 'T00:00:00'), "MMM d")}
                              </span>
                              <div className="flex-1">
                                <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-4 relative">
                                  <div
                                    className="bg-gradient-to-r from-blue-500 to-blue-600 h-4 rounded-full transition-all flex items-center justify-end pr-2"
                                    style={{ width: `${getBarWidth(day.treatedPatients, maxPatients)}%` }}
                                  >
                                    {day.treatedPatients > 0 && (
                                      <span className="text-[10px] text-white font-medium">{day.treatedPatients}</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <span className="text-xs text-gray-600 w-16 text-right shrink-0">
                                {day.totalProcedures} proc.
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            )}

            {reportView === "procedures" && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Procedure Breakdown</CardTitle>
                  <CardDescription>
                    {selectedDoctorFilter === "all"
                      ? "Complete procedure counts for the entire department"
                      : `Procedure counts for ${departmentDoctors.find(d => d.id.toString() === selectedDoctorFilter)?.name || "selected doctor"}`}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-3 px-4 font-medium">Procedure</th>
                          {selectedDoctorFilter === "all" && stats.perDoctor.map(d => (
                            <th key={d.doctor.id} className="text-center py-3 px-2 font-medium min-w-[80px]">
                              <div className="truncate max-w-[100px]" title={d.doctor.name}>
                                {d.doctor.name.split(" ").slice(-1)[0]}
                              </div>
                            </th>
                          ))}
                          <th className="text-center py-3 px-4 font-bold bg-blue-50 dark:bg-blue-900/20">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b bg-green-50 dark:bg-green-900/10 font-medium">
                          <td className="py-3 px-4 flex items-center gap-2">
                            <Users className="h-4 w-4 text-green-600" />
                            Treated Patients
                          </td>
                          {selectedDoctorFilter === "all" && stats.perDoctor.map(d => (
                            <td key={d.doctor.id} className="text-center py-3 px-2">
                              <span className="font-semibold">{d.treatedPatients}</span>
                            </td>
                          ))}
                          <td className="text-center py-3 px-4 font-bold bg-blue-50 dark:bg-blue-900/20">
                            {stats.departmentTotals.treatedPatients}
                          </td>
                        </tr>
                        {procedureKeys.map(key => {
                          const total = stats.departmentTotals.procedureTotals[key] || 0;
                          return (
                            <tr key={key} className={`border-b hover:bg-gray-50 dark:hover:bg-gray-800 ${total === 0 ? "opacity-50" : ""}`}>
                              <td className="py-2 px-4">{procedureLabels[key]}</td>
                              {selectedDoctorFilter === "all" && stats.perDoctor.map(d => {
                                const val = d.procedureTotals[key] || 0;
                                return (
                                  <td key={d.doctor.id} className="text-center py-2 px-2">
                                    {val > 0 ? (
                                      <Badge variant="secondary" className="text-xs">{val}</Badge>
                                    ) : (
                                      <span className="text-gray-300">-</span>
                                    )}
                                  </td>
                                );
                              })}
                              <td className="text-center py-2 px-4 font-semibold bg-blue-50 dark:bg-blue-900/20">
                                {total > 0 ? total : "-"}
                              </td>
                            </tr>
                          );
                        })}
                        <tr className="border-t-2 font-bold bg-gray-50 dark:bg-gray-800">
                          <td className="py-3 px-4">Grand Total (Procedures)</td>
                          {selectedDoctorFilter === "all" && stats.perDoctor.map(d => {
                            const docTotal = Object.values(d.procedureTotals).reduce((s, v) => s + v, 0);
                            return (
                              <td key={d.doctor.id} className="text-center py-3 px-2">{docTotal}</td>
                            );
                          })}
                          <td className="text-center py-3 px-4 bg-blue-50 dark:bg-blue-900/20">{totalProcedures}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {reportView === "doctors" && (
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Doctor Comparison</CardTitle>
                    <CardDescription>Side-by-side performance of each doctor in the department</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {stats.perDoctor
                        .sort((a, b) => b.treatedPatients - a.treatedPatients)
                        .map((d, i) => {
                          const docProcedureTotal = Object.values(d.procedureTotals).reduce((s, v) => s + v, 0);
                          const topProcedure = procedureKeys
                            .map(k => ({ key: k, count: d.procedureTotals[k] || 0 }))
                            .sort((a, b) => b.count - a.count)[0];
                          const maxPatients = Math.max(...stats.perDoctor.map(x => x.treatedPatients), 1);

                          return (
                            <Card key={d.doctor.id} className={`${i === 0 && stats.perDoctor.length > 1 ? "ring-2 ring-yellow-400" : ""}`}>
                              <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                  <div>
                                    <CardTitle className="text-base">{d.doctor.name}</CardTitle>
                                    <CardDescription className="text-xs">{d.doctor.title}</CardDescription>
                                  </div>
                                  {i === 0 && stats.perDoctor.length > 1 && d.treatedPatients > 0 && (
                                    <Badge className="bg-yellow-500 text-white">Top</Badge>
                                  )}
                                </div>
                              </CardHeader>
                              <CardContent>
                                <div className="space-y-3">
                                  <div>
                                    <div className="flex justify-between text-sm mb-1">
                                      <span>Patients Treated</span>
                                      <span className="font-bold">{d.treatedPatients}</span>
                                    </div>
                                    <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                                      <div
                                        className="bg-blue-600 h-2 rounded-full"
                                        style={{ width: `${getBarWidth(d.treatedPatients, maxPatients)}%` }}
                                      />
                                    </div>
                                  </div>
                                  <div className="flex justify-between text-sm">
                                    <span className="text-gray-500">Completed Visits</span>
                                    <span>{d.completedAppointments}</span>
                                  </div>
                                  <div className="flex justify-between text-sm">
                                    <span className="text-gray-500">Total Procedures</span>
                                    <span>{docProcedureTotal}</span>
                                  </div>
                                  {topProcedure && topProcedure.count > 0 && (
                                    <div className="pt-2 border-t">
                                      <p className="text-xs text-gray-500">Top Procedure</p>
                                      <p className="text-sm font-medium">
                                        {procedureLabels[topProcedure.key]} ({topProcedure.count})
                                      </p>
                                    </div>
                                  )}
                                </div>
                              </CardContent>
                            </Card>
                          );
                        })}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Patients Treated Ranking</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {stats.perDoctor
                        .sort((a, b) => b.treatedPatients - a.treatedPatients)
                        .map((d, i) => {
                          const maxP = Math.max(...stats.perDoctor.map(x => x.treatedPatients), 1);
                          return (
                            <div key={d.doctor.id} className="flex items-center gap-4">
                              <span className={`text-lg font-bold w-8 text-center ${i === 0 ? "text-yellow-500" : i === 1 ? "text-gray-400" : i === 2 ? "text-amber-600" : "text-gray-300"}`}>
                                {i + 1}
                              </span>
                              <div className="flex-1">
                                <div className="flex justify-between mb-1">
                                  <span className="font-medium">{d.doctor.name}</span>
                                  <span className="font-bold">{d.treatedPatients} patients</span>
                                </div>
                                <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-3">
                                  <div
                                    className={`h-3 rounded-full transition-all ${i === 0 ? "bg-yellow-500" : i === 1 ? "bg-gray-400" : i === 2 ? "bg-amber-600" : "bg-blue-400"}`}
                                    style={{ width: `${getBarWidth(d.treatedPatients, maxP)}%` }}
                                  />
                                </div>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {reportView === "strengths" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <ThumbsUp className="h-5 w-5 text-green-600" />
                      <CardTitle className="text-lg text-green-700">Department Strengths</CardTitle>
                    </div>
                    <CardDescription>Procedures where the department excels</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {strengths.length === 0 ? (
                      <p className="text-gray-500 text-center py-8">No procedure data to analyze</p>
                    ) : (
                      <div className="space-y-4">
                        {strengths.map((proc, i) => {
                          const doctorsDoingThis = stats.perDoctor
                            .filter(d => (d.procedureTotals[proc.key] || 0) > 0)
                            .sort((a, b) => (b.procedureTotals[proc.key] || 0) - (a.procedureTotals[proc.key] || 0));
                          return (
                            <div key={proc.key} className="p-3 bg-green-50 dark:bg-green-900/10 rounded-lg">
                              <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2">
                                  <ChevronUp className="h-4 w-4 text-green-600" />
                                  <span className="font-medium">{proc.label}</span>
                                </div>
                                <Badge className="bg-green-600">{proc.count} total</Badge>
                              </div>
                              <div className="text-xs text-gray-500">
                                Performed by {doctorsDoingThis.length} doctor{doctorsDoingThis.length !== 1 ? "s" : ""}
                                {doctorsDoingThis.length > 0 && (
                                  <span> - Top: {doctorsDoingThis[0].doctor.name} ({doctorsDoingThis[0].procedureTotals[proc.key]})</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <ThumbsDown className="h-5 w-5 text-orange-600" />
                      <CardTitle className="text-lg text-orange-700">Areas for Improvement</CardTitle>
                    </div>
                    <CardDescription>Procedures with low activity that may need attention</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {weaknesses.length === 0 ? (
                      <p className="text-gray-500 text-center py-8">
                        {totalProcedures === 0 ? "No procedure data to analyze" : "All procedures are well-covered"}
                      </p>
                    ) : (
                      <div className="space-y-4">
                        {weaknesses.map(proc => {
                          const doctorsDoingThis = stats.perDoctor
                            .filter(d => (d.procedureTotals[proc.key] || 0) > 0);
                          const doctorsNotDoing = stats.perDoctor.length - doctorsDoingThis.length;
                          return (
                            <div key={proc.key} className="p-3 bg-orange-50 dark:bg-orange-900/10 rounded-lg">
                              <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2">
                                  <ChevronDown className="h-4 w-4 text-orange-600" />
                                  <span className="font-medium">{proc.label}</span>
                                </div>
                                <Badge variant="outline" className="text-orange-600 border-orange-300">
                                  {proc.count} total
                                </Badge>
                              </div>
                              <div className="text-xs text-gray-500">
                                {proc.count === 0 ? (
                                  "No activity recorded - consider training or patient referral review"
                                ) : (
                                  <>
                                    Only {doctorsDoingThis.length} of {stats.perDoctor.length} doctors performing this procedure
                                    {doctorsNotDoing > 0 && ` - ${doctorsNotDoing} doctor${doctorsNotDoing > 1 ? "s" : ""} with no activity`}
                                  </>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="lg:col-span-2">
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Activity className="h-5 w-5 text-blue-600" />
                      <CardTitle className="text-lg">Department Summary</CardTitle>
                    </div>
                    <CardDescription>
                      Overall assessment for {startDate} to {endDate}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/10 rounded-lg">
                        <p className="text-sm text-gray-500 mb-1">Procedure Coverage</p>
                        <p className="text-3xl font-bold text-blue-600">
                          {sortedProcedures.filter(p => p.count > 0).length} / {procedureKeys.length}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {Math.round((sortedProcedures.filter(p => p.count > 0).length / procedureKeys.length) * 100)}% of procedures active
                        </p>
                      </div>

                      <div className="text-center p-4 bg-green-50 dark:bg-green-900/10 rounded-lg">
                        <p className="text-sm text-gray-500 mb-1">Doctor Productivity</p>
                        <p className="text-3xl font-bold text-green-600">
                          {avgPatientsPerDoctor}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Average patients per active doctor
                        </p>
                      </div>

                      <div className="text-center p-4 bg-purple-50 dark:bg-purple-900/10 rounded-lg">
                        <p className="text-sm text-gray-500 mb-1">Procedures per Patient</p>
                        <p className="text-3xl font-bold text-purple-600">
                          {stats.departmentTotals.treatedPatients > 0
                            ? (totalProcedures / stats.departmentTotals.treatedPatients).toFixed(1)
                            : "0"}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Average procedures per patient visit
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
