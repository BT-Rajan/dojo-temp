import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Lock, Eye, EyeOff, CheckCircle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";

interface Props { departmentId: number }

export default function CallCenterCodeCard({ departmentId }: Props) {
  const { toast } = useToast();
  const [code, setCode] = useState("");
  const [show, setShow] = useState(false);
  const [saved, setSaved] = useState(false);

  const setCode_ = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/callcenter/set-code", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ departmentId, code: code.trim() }),
      });
      if (!res.ok) throw new Error((await res.json()).message || "Failed");
      return res.json();
    },
    onSuccess: () => {
      setSaved(true);
      toast({ title: "Call center code updated", description: "The new code is now active." });
      setTimeout(() => setSaved(false), 3000);
    },
    onError: (e: any) => toast({ title: e.message || "Failed to save", variant: "destructive" }),
  });

  return (
    <Card className="card-hover glass-effect rounded-2xl overflow-hidden border-violet-100">
      <CardHeader className="pb-4">
        <div className="p-3 bg-violet-100 rounded-xl w-fit mb-4">
          <Lock className="h-8 w-8 text-violet-600" />
        </div>
        <CardTitle className="text-xl">Call Center Access Code</CardTitle>
        <CardDescription className="text-gray-600">
          Set the secret code that call center staff use to access the examination schedule
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label className="text-sm">New Access Code</Label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                type={show ? "text" : "password"}
                placeholder="Enter new code..."
                value={code}
                onChange={e => setCode(e.target.value)}
                className="pr-9"
              />
              <button
                type="button"
                onClick={() => setShow(!show)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <Button
              onClick={() => setCode_.mutate()}
              disabled={!code.trim() || setCode_.isPending}
              className={saved ? "bg-green-600 hover:bg-green-700 text-white" : "bg-violet-600 hover:bg-violet-700 text-white"}
            >
              {saved ? <><CheckCircle className="w-4 h-4 mr-1" />Saved</> : setCode_.isPending ? "Saving..." : "Save Code"}
            </Button>
          </div>
        </div>
        <p className="text-[11px] text-gray-400">Share this code with your call center team so they can log in to manage examination appointments.</p>
      </CardContent>
    </Card>
  );
}
