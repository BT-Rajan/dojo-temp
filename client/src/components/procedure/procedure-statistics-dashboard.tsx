import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Calendar, BarChart3, TrendingUp, User, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";

interface ProcedureStats {
  doctor?: {
    id: number;
    name: string;
    title: string;
  };
  totalAppointments: number;
  completedAppointments: number;
  procedureTotals: Record<string, number>;
}

interface ProcedureStatisticsProps {
  departmentId?: number;
  doctorId?: number;
  showDoctorFilter?: boolean;
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
};

export function ProcedureStatisticsDashboard({ departmentId, doctorId, showDoctorFilter = true }: ProcedureStatisticsProps) {
  const currentDate = new Date();
  const [selectedYear, setSelectedYear] = useState(currentDate.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(currentDate.getMonth() + 1);
  const [selectedDoctorId, setSelectedDoctorId] = useState<number | undefined>(doctorId);

  // Fetch department doctors if showing doctor filter
  const { data: doctors = [] } = useQuery({
    queryKey: [`/api/doctors?departmentId=${departmentId}`],
    enabled: showDoctorFilter && !!departmentId,
  });

  // Build API URL based on selection
  const buildStatsUrl = () => {
    if (selectedDoctorId) {
      return `/api/procedure-stats/doctor/${selectedDoctorId}?year=${selectedYear}&month=${selectedMonth}`;
    } else if (departmentId) {
      return `/api/procedure-stats/department/${departmentId}?year=${selectedYear}&month=${selectedMonth}`;
    }
    return null;
  };

  const { data: procedureStats, isLoading } = useQuery<ProcedureStats | ProcedureStats[]>({
    queryKey: [buildStatsUrl()],
    enabled: !!buildStatsUrl(),
  });

  const formatMonthYear = (month: number, year: number) => {
    return format(new Date(year, month - 1, 1), 'MMMM yyyy');
  };

  const getTotalProcedures = (stats: ProcedureStats) => {
    return Object.values(stats.procedureTotals).reduce((sum, count) => sum + count, 0);
  };

  const renderDoctorStats = (stats: ProcedureStats, isIndividual = false) => (
    <Card key={stats.doctor?.id || 'individual'} className="w-full" data-testid={`card-doctor-stats-${stats.doctor?.id || 'individual'}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-blue-600" />
            <CardTitle className="text-lg">
              {isIndividual ? 'Your Statistics' : `${stats.doctor?.title || ''} ${stats.doctor?.name || 'Unknown'}`}
            </CardTitle>
          </div>
          <Badge variant="secondary" data-testid={`badge-total-procedures-${stats.doctor?.id || 'individual'}`}>
            {getTotalProcedures(stats)} Total Procedures
          </Badge>
        </div>
        <CardDescription>
          Performance for {formatMonthYear(selectedMonth, selectedYear)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <Calendar className="h-4 w-4 text-blue-600" />
            <div>
              <p className="text-sm font-medium">Total Appointments</p>
              <p className="text-xl font-bold" data-testid={`text-total-appointments-${stats.doctor?.id || 'individual'}`}>
                {stats.totalAppointments}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <TrendingUp className="h-4 w-4 text-green-600" />
            <div>
              <p className="text-sm font-medium">Completed</p>
              <p className="text-xl font-bold" data-testid={`text-completed-appointments-${stats.doctor?.id || 'individual'}`}>
                {stats.completedAppointments}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
            <BarChart3 className="h-4 w-4 text-orange-600" />
            <div>
              <p className="text-sm font-medium">Completion Rate</p>
              <p className="text-xl font-bold" data-testid={`text-completion-rate-${stats.doctor?.id || 'individual'}`}>
                {stats.totalAppointments > 0 
                  ? Math.round((stats.completedAppointments / stats.totalAppointments) * 100)
                  : 0}%
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <h4 className="font-medium flex items-center gap-2 mb-3">
            <FileText className="h-4 w-4" />
            Procedure Breakdown
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {Object.entries(procedureLabels).map(([key, label]) => {
              const count = stats.procedureTotals[key] || 0;
              if (count === 0) return null;
              
              return (
                <div 
                  key={key} 
                  className="flex justify-between items-center p-2 bg-gray-50 dark:bg-gray-800 rounded"
                  data-testid={`procedure-${key}-${stats.doctor?.id || 'individual'}`}
                >
                  <span className="text-sm">{label}</span>
                  <Badge variant="outline">{count}</Badge>
                </div>
              );
            })}
          </div>
          {getTotalProcedures(stats) === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">
              No procedures recorded for this period.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );

  if (isLoading) {
    return (
      <Card className="w-full">
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-2">Loading procedure statistics...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Procedure Statistics
          </CardTitle>
          <CardDescription>
            View detailed procedure statistics and performance metrics
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">Year:</label>
              <Select value={selectedYear.toString()} onValueChange={(value) => setSelectedYear(parseInt(value))}>
                <SelectTrigger className="w-24" data-testid="select-year">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 5 }, (_, i) => currentDate.getFullYear() - i).map(year => (
                    <SelectItem key={year} value={year.toString()}>{year}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">Month:</label>
              <Select value={selectedMonth.toString()} onValueChange={(value) => setSelectedMonth(parseInt(value))}>
                <SelectTrigger className="w-32" data-testid="select-month">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(month => (
                    <SelectItem key={month} value={month.toString()}>
                      {format(new Date(2025, month - 1, 1), 'MMMM')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {showDoctorFilter && (
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium">Doctor:</label>
                <Select 
                  value={selectedDoctorId?.toString() || "all"} 
                  onValueChange={(value) => setSelectedDoctorId(value === "all" ? undefined : parseInt(value))}
                >
                  <SelectTrigger className="w-48" data-testid="select-doctor">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Doctors</SelectItem>
                    {doctors.map((doctor: any) => (
                      <SelectItem key={doctor.id} value={doctor.id.toString()}>
                        {doctor.title} {doctor.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Statistics Display */}
      <div className="space-y-4">
        {Array.isArray(procedureStats) ? (
          procedureStats.length > 0 ? (
            procedureStats.map(stats => renderDoctorStats(stats))
          ) : (
            <Card>
              <CardContent className="p-6 text-center">
                <p className="text-gray-500">No procedure data found for the selected period.</p>
              </CardContent>
            </Card>
          )
        ) : procedureStats ? (
          renderDoctorStats(procedureStats, true)
        ) : (
          <Card>
            <CardContent className="p-6 text-center">
              <p className="text-gray-500">No procedure data found for the selected period.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}