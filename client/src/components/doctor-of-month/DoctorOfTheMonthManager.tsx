import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Trophy, Award, Calendar, TrendingUp, User, Star } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface Doctor {
  id: number;
  name: string;
  title: string;
  email: string;
  phone: string;
  departmentId: number;
}

interface DoctorOfTheMonthAward {
  id: number;
  doctorId: number;
  departmentId: number;
  year: number;
  month: number;
  totalAppointments: number;
  completedAppointments: number;
  completionRate: number;
  patientSatisfactionScore: number;
  punctualityScore: number;
  overallScore: number;
  certificateGenerated: boolean;
  certificateUrl: string | null;
  awardedAt: string;
  createdAt: string;
  doctor: Doctor;
}

interface DoctorRanking {
  doctorId: number;
  doctor: Doctor;
  totalAppointments: number;
  completedAppointments: number;
  completionRate: number;
  overallScore: number;
}

interface DoctorOfTheMonthManagerProps {
  departmentId: number;
}

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

export default function DoctorOfTheMonthManager({ departmentId }: DoctorOfTheMonthManagerProps) {
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Queries
  const { data: awards = [] } = useQuery<DoctorOfTheMonthAward[]>({
    queryKey: [`/api/departments/${departmentId}/doctor-of-month/awards`],
  });

  const { data: currentAward } = useQuery<DoctorOfTheMonthAward | null>({
    queryKey: [`/api/departments/${departmentId}/doctor-of-month/current`],
  });

  const { data: rankings = [] } = useQuery<DoctorRanking[]>({
    queryKey: [`/api/departments/${departmentId}/doctor-rankings/${selectedYear}/${selectedMonth}`],
  });

  // Mutation for creating awards
  const createAwardMutation = useMutation({
    mutationFn: async ({ doctorId, year, month }: { doctorId: number; year: number; month: number }) => {
      const response = await fetch(`/api/departments/${departmentId}/doctor-of-month/award`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doctorId, year, month }),
      });
      if (!response.ok) {
        throw new Error('Failed to create award');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [`/api/departments/${departmentId}/doctor-of-month/awards`] });
      queryClient.invalidateQueries({ queryKey: [`/api/departments/${departmentId}/doctor-of-month/current`] });
      toast({
        title: "Award Created",
        description: "Doctor of the Month award has been successfully created!",
        variant: "default",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to create award. Please try again.",
        variant: "destructive",
      });
    },
  });

  const handleCreateAward = (doctorId: number) => {
    createAwardMutation.mutate({
      doctorId,
      year: selectedYear,
      month: selectedMonth,
    });
  };

  const getMonthName = (month: number) => {
    return MONTHS.find(m => m.value === month)?.label || '';
  };

  const formatCompletionRate = (rate: number) => {
    return `${Math.round(rate)}%`;
  };

  const getRankingColor = (index: number) => {
    switch (index) {
      case 0: return 'bg-yellow-100 border-yellow-400 text-yellow-800';
      case 1: return 'bg-gray-100 border-gray-400 text-gray-800';
      case 2: return 'bg-orange-100 border-orange-400 text-orange-800';
      default: return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  const getRankingIcon = (index: number) => {
    switch (index) {
      case 0: return <Trophy className="h-5 w-5 text-yellow-600" />;
      case 1: return <Award className="h-5 w-5 text-gray-600" />;
      case 2: return <Star className="h-5 w-5 text-orange-600" />;
      default: return <User className="h-5 w-5 text-blue-600" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Trophy className="h-6 w-6 text-yellow-600" />
            Doctor of the Month
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Recognize outstanding performance and motivate excellence
          </p>
        </div>
      </div>

      <Tabs defaultValue="current" className="space-y-4">
        <TabsList>
          <TabsTrigger value="current">Current Award</TabsTrigger>
          <TabsTrigger value="rankings">Monthly Rankings</TabsTrigger>
          <TabsTrigger value="history">Award History</TabsTrigger>
        </TabsList>

        {/* Current Award Tab */}
        <TabsContent value="current" className="space-y-4">
          {currentAward ? (
            <Card className="bg-gradient-to-r from-yellow-50 to-orange-50 border-yellow-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-6 w-6 text-yellow-600" />
                  Doctor of the Month - {getMonthName(currentAward.month)} {currentAward.year}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900">{currentAward.doctor.name}</h3>
                    <p className="text-gray-600">{currentAward.doctor.title}</p>
                    <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="font-medium">Total Appointments:</span> {currentAward.totalAppointments}
                      </div>
                      <div>
                        <span className="font-medium">Completed:</span> {currentAward.completedAppointments}
                      </div>
                      <div>
                        <span className="font-medium">Completion Rate:</span> {formatCompletionRate(currentAward.completionRate)}
                      </div>
                      <div>
                        <span className="font-medium">Overall Score:</span> {currentAward.overallScore.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="bg-yellow-100 rounded-full p-4 mb-2">
                      <Trophy className="h-12 w-12 text-yellow-600 mx-auto" />
                    </div>
                    <Badge className="bg-yellow-200 text-yellow-800 hover:bg-yellow-200">
                      Champion
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="text-center py-8">
                <Trophy className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
                  No Award for This Month
                </h3>
                <p className="text-gray-600 dark:text-gray-400">
                  Select a doctor from the rankings to create this month's award.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Rankings Tab */}
        <TabsContent value="rankings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Performance Rankings
                </span>
                <div className="flex items-center gap-2">
                  <Select value={selectedMonth.toString()} onValueChange={(value) => setSelectedMonth(parseInt(value))}>
                    <SelectTrigger className="w-32">
                      <SelectValue placeholder="Month" />
                    </SelectTrigger>
                    <SelectContent>
                      {MONTHS.map(month => (
                        <SelectItem key={month.value} value={month.value.toString()}>
                          {month.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={selectedYear.toString()} onValueChange={(value) => setSelectedYear(parseInt(value))}>
                    <SelectTrigger className="w-24">
                      <SelectValue placeholder="Year" />
                    </SelectTrigger>
                    <SelectContent>
                      {[2024, 2025, 2026].map(year => (
                        <SelectItem key={year} value={year.toString()}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {rankings.length > 0 ? rankings.map((ranking, index) => (
                  <Card key={ranking.doctorId} className={`p-4 ${getRankingColor(index)}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getRankingIcon(index)}
                        <div>
                          <h4 className="font-semibold">{ranking.doctor.name}</h4>
                          <p className="text-sm opacity-80">{ranking.doctor.title}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <div className="font-medium">{ranking.totalAppointments}</div>
                            <div className="text-xs opacity-70">Total</div>
                          </div>
                          <div>
                            <div className="font-medium">{formatCompletionRate(ranking.completionRate)}</div>
                            <div className="text-xs opacity-70">Rate</div>
                          </div>
                          <div>
                            <div className="font-medium">{ranking.overallScore.toFixed(1)}</div>
                            <div className="text-xs opacity-70">Score</div>
                          </div>
                        </div>
                      </div>
                      <div className="ml-4">
                        {index === 0 && !currentAward && (
                          <Button
                            onClick={() => handleCreateAward(ranking.doctorId)}
                            disabled={createAwardMutation.isPending}
                            size="sm"
                            className="bg-yellow-600 hover:bg-yellow-700"
                          >
                            <Trophy className="h-4 w-4 mr-1" />
                            Award
                          </Button>
                        )}
                      </div>
                    </div>
                  </Card>
                )) : (
                  <div className="text-center py-8">
                    <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 dark:text-gray-400">
                      No performance data available for {getMonthName(selectedMonth)} {selectedYear}
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                Award History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {awards.length > 0 ? awards.map((award) => (
                  <Card key={award.id} className="p-4 border-l-4 border-l-yellow-400">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-semibold">{award.doctor.name}</h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {getMonthName(award.month)} {award.year} • {award.doctor.title}
                        </p>
                        <div className="mt-2 flex items-center gap-4 text-sm">
                          <span className="bg-green-100 text-green-800 px-2 py-1 rounded-full">
                            {formatCompletionRate(award.completionRate)} completion
                          </span>
                          <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                            {award.overallScore.toFixed(1)} score
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <Trophy className="h-6 w-6 text-yellow-600 mx-auto" />
                        <p className="text-xs text-gray-500 mt-1">
                          {new Date(award.awardedAt).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </Card>
                )) : (
                  <div className="text-center py-8">
                    <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 dark:text-gray-400">
                      No awards have been given yet.
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}