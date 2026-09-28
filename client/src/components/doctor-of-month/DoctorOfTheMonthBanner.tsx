import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Trophy, Star } from 'lucide-react';

interface Doctor {
  id: number;
  name: string;
  title: string;
  email: string;
  phone: string;
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
  overallScore: number;
  awardedAt: string;
  doctor: Doctor;
}

interface DoctorOfTheMonthBannerProps {
  departmentId: number;
  className?: string;
}

const MONTHS = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export default function DoctorOfTheMonthBanner({ departmentId, className = '' }: DoctorOfTheMonthBannerProps) {
  const { data: currentAward } = useQuery<DoctorOfTheMonthAward | null>({
    queryKey: [`/api/departments/${departmentId}/doctor-of-month/current`],
  });

  if (!currentAward) {
    return null;
  }

  return (
    <Card className={`bg-gradient-to-r from-yellow-50 via-yellow-100 to-orange-50 border-yellow-200 shadow-md ${className}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-yellow-200 rounded-full p-2">
              <Trophy className="h-6 w-6 text-yellow-700" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-yellow-900">Doctor of the Month</h3>
                <Badge className="bg-yellow-300 text-yellow-800 hover:bg-yellow-300 text-xs">
                  {MONTHS[currentAward.month]} {currentAward.year}
                </Badge>
              </div>
              <p className="text-yellow-800">
                <span className="font-medium">{currentAward.doctor.name}</span>
                {" • "}
                <span className="text-sm">{currentAward.doctor.title}</span>
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-1 text-yellow-700">
              <Star className="h-4 w-4 fill-current" />
              <span className="font-semibold">{currentAward.overallScore.toFixed(1)}</span>
            </div>
            <p className="text-xs text-yellow-600">
              {Math.round(currentAward.completionRate)}% completion
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}