import { format, addDays, startOfWeek, isToday, parseISO } from "date-fns";

export function getWeekdayName(weekday: number): string {
  const weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  return weekdays[weekday] || "";
}

export function getTodayWeekday(): number {
  return new Date().getDay();
}

export function formatDate(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, "MMM dd, yyyy");
  } catch (error) {
    return dateString;
  }
}

export function formatTime(timeString: string): string {
  try {
    const [hours, minutes] = timeString.split(':');
    const date = new Date();
    date.setHours(parseInt(hours), parseInt(minutes));
    return format(date, "h:mm a");
  } catch (error) {
    return timeString;
  }
}

export function isDateToday(dateString: string): boolean {
  try {
    const date = parseISO(dateString);
    return isToday(date);
  } catch (error) {
    return false;
  }
}

export function getWeekRange(date: Date = new Date()): { start: Date; end: Date } {
  const start = startOfWeek(date, { weekStartsOn: 0 }); // Sunday
  const end = addDays(start, 4); // Thursday (working days)
  return { start, end };
}

export function getDaysBetween(startDate: string, endDate: string): number {
  try {
    const start = parseISO(startDate);
    const end = parseISO(endDate);
    const diffTime = Math.abs(end.getTime() - start.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays + 1; // Include both start and end dates
  } catch (error) {
    return 0;
  }
}

export function isDateInRange(date: string, startDate: string, endDate: string): boolean {
  try {
    const checkDate = parseISO(date);
    const start = parseISO(startDate);
    const end = parseISO(endDate);
    return checkDate >= start && checkDate <= end;
  } catch (error) {
    return false;
  }
}

export function getCurrentMonthYear(): { year: number; month: number } {
  const now = new Date();
  return {
    year: now.getFullYear(),
    month: now.getMonth() + 1, // JavaScript months are 0-indexed
  };
}

export function getWorkingDays(): number[] {
  return [0, 1, 2, 3, 4]; // Sunday through Thursday
}

export function isWorkingDay(weekday: number): boolean {
  return getWorkingDays().includes(weekday);
}
