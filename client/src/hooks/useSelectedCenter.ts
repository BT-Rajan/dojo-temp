export function useSelectedCenter(): string {
  return localStorage.getItem("selectedCenterId") || "";
}
