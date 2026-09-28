import { useQuery } from "@tanstack/react-query";
import type { Center } from "@shared/schema";

export function useCenterName() {
  const selectedCenterId = localStorage.getItem("selectedCenterId");

  const { data: userCenters = [] } = useQuery<Center[]>({
    queryKey: ["/api/user/centers"],
  });

  const selectedCenter = userCenters.find(c => c.id.toString() === selectedCenterId);

  return {
    centerName: selectedCenter?.name || userCenters[0]?.name || "Medical Center"
  };
}
