import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { ClipboardCheck, Stethoscope } from "lucide-react";

interface ProcedureData {
  treatedPatients: number;
  alginatePreparation: number;
  crownPreparation: number;
  bridgePreparation: number;
  finalImpression: number;
  tempCementation: number;
  cementAccBb: number;
  cementPorcelainCb: number;
  metalCrownCb: number;
  porcelainCb: number;
  postPreparation: number;
  postCanal: number;
  compositeFilling: number;
  amalgamFilling: number;
  removableProstho: number;
  removableProsthoRepair: number;
  cbRemovalPostCore: number;
  orthoAppliances: number;
  buckleAppointment: number;
  implantUnits: number;
  tryIn: number;
  miscellaneous: number;
  examination: number;
}

interface ProcedureQuestionnaireProps {
  appointmentId: number;
  doctorId: number;
  departmentId: number;
  appointmentDate: string;
  onComplete: () => void;
  onCancel: () => void;
}

const procedureFields = [
  { key: "treatedPatients", label: "Treated Patients", icon: "👥" },
  { key: "alginatePreparation", label: "Alginate Preparation", icon: "🧪" },
  { key: "crownPreparation", label: "Crown Preparation", icon: "👑" },
  { key: "bridgePreparation", label: "Bridge Preparation", icon: "🌉" },
  { key: "finalImpression", label: "Final Impression", icon: "🖨️" },
  { key: "tempCementation", label: "Temp. Cementation", icon: "🔧" },
  { key: "cementAccBb", label: "Cement ACC & BB", icon: "🧱" },
  { key: "cementPorcelainCb", label: "Cement Porcelain C&B", icon: "🦷" },
  { key: "metalCrownCb", label: "Metal Crown C&B", icon: "⚙️" },
  { key: "porcelainCb", label: "Porcelain C&B", icon: "💎" },
  { key: "postPreparation", label: "Post Preparation", icon: "📍" },
  { key: "postCanal", label: "Post Canal", icon: "🔌" },
  { key: "compositeFilling", label: "Composite Filling", icon: "🎨" },
  { key: "amalgamFilling", label: "Amalgam Filling", icon: "⚪" },
  { key: "removableProstho", label: "Removable Prostho.", icon: "🦷" },
  { key: "removableProsthoRepair", label: "Removable Prostho. Repair", icon: "🔨" },
  { key: "cbRemovalPostCore", label: "C&B Removal / Post & Core", icon: "🗑️" },
  { key: "orthoAppliances", label: "Ortho Appliances", icon: "🦷" },
  { key: "buckleAppointment", label: "Buckle Appointment", icon: "📋" },
  { key: "implantUnits", label: "Implant Units", icon: "🔩" },
  { key: "tryIn", label: "Try-In", icon: "🔍" },
  { key: "miscellaneous", label: "Miscellaneous", icon: "📝" },
  { key: "examination", label: "Examination", icon: "🩺" },
] as const;

export function ProcedureQuestionnaire({
  appointmentId,
  doctorId,
  departmentId,
  appointmentDate,
  onComplete,
  onCancel,
}: ProcedureQuestionnaireProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  const [procedureData, setProcedureData] = useState<ProcedureData>({
    treatedPatients: 1, // Default to 1 since this appointment treated a patient
    alginatePreparation: 0,
    crownPreparation: 0,
    bridgePreparation: 0,
    finalImpression: 0,
    tempCementation: 0,
    cementAccBb: 0,
    cementPorcelainCb: 0,
    metalCrownCb: 0,
    porcelainCb: 0,
    postPreparation: 0,
    postCanal: 0,
    compositeFilling: 0,
    amalgamFilling: 0,
    removableProstho: 0,
    removableProsthoRepair: 0,
    cbRemovalPostCore: 0,
    orthoAppliances: 0,
    buckleAppointment: 0,
    implantUnits: 0,
    tryIn: 0,
    miscellaneous: 0,
    examination: 0,
  });

  const saveProcedureMutation = useMutation({
    mutationFn: async () => {
      return await apiRequest(`/api/procedure-logs`, {
        method: "POST",
        body: JSON.stringify({
          appointmentId,
          doctorId,
          departmentId,
          procedureDate: appointmentDate,
          ...procedureData,
        }),
      });
    },
    onSuccess: () => {
      toast({
        title: "Procedures Logged",
        description: "Your procedure data has been saved successfully.",
      });
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ["/api/appointments"] });
      queryClient.invalidateQueries({ queryKey: ["/api/procedure-logs"] });
      onComplete();
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: `Failed to save procedure data: ${error.message}`,
        variant: "destructive",
      });
    },
  });

  const handleInputChange = (field: keyof ProcedureData, value: string) => {
    const numValue = parseInt(value) || 0;
    setProcedureData(prev => ({
      ...prev,
      [field]: Math.max(0, numValue) // Ensure non-negative values
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    saveProcedureMutation.mutate();
  };

  const handleSkip = () => {
    // Save with all zeros except treated patients
    const emptyData = {
      treatedPatients: 1,
      alginatePreparation: 0,
      crownPreparation: 0,
      bridgePreparation: 0,
      finalImpression: 0,
      tempCementation: 0,
      cementAccBb: 0,
      cementPorcelainCb: 0,
      metalCrownCb: 0,
      porcelainCb: 0,
      postPreparation: 0,
      postCanal: 0,
      compositeFilling: 0,
      amalgamFilling: 0,
      removableProstho: 0,
      removableProsthoRepair: 0,
      cbRemovalPostCore: 0,
      orthoAppliances: 0,
      buckleAppointment: 0,
      implantUnits: 0,
      tryIn: 0,
      miscellaneous: 0,
      examination: 0,
    };
    setProcedureData(emptyData);
    setTimeout(() => saveProcedureMutation.mutate(), 100);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="procedure-questionnaire-modal">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Stethoscope className="h-6 w-6 text-blue-600" />
            <CardTitle className="text-xl">Procedure Log</CardTitle>
          </div>
          <CardDescription>
            Please log the dental procedures performed during this appointment.
            <br />
            <span className="text-sm text-gray-600">
              This data helps track your monthly statistics and performance metrics.
            </span>
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {procedureFields.map(({ key, label, icon }) => (
                <div key={key} className="space-y-2">
                  <Label htmlFor={key} className="text-sm font-medium flex items-center gap-2">
                    <span className="text-lg">{icon}</span>
                    {label}
                  </Label>
                  <Input
                    id={key}
                    type="number"
                    min="0"
                    max="999"
                    value={procedureData[key]}
                    onChange={(e) => handleInputChange(key, e.target.value)}
                    className="w-full"
                    data-testid={`input-${key}`}
                  />
                </div>
              ))}
            </div>
            
            <div className="flex items-center justify-between pt-6 border-t">
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  disabled={saveProcedureMutation.isPending}
                  data-testid="button-cancel-procedure"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleSkip}
                  disabled={saveProcedureMutation.isPending}
                  data-testid="button-skip-procedure"
                >
                  Skip Logging
                </Button>
              </div>
              
              <Button
                type="submit"
                disabled={saveProcedureMutation.isPending}
                className="flex items-center gap-2"
                data-testid="button-save-procedure"
              >
                <ClipboardCheck className="h-4 w-4" />
                {saveProcedureMutation.isPending ? "Saving..." : "Save Procedures"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}