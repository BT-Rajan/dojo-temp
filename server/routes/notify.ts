import { wsConnections } from "../index";

// Utility function to send WebSocket notifications
export function sendNotificationToDoctor(doctorId: number, notification: any) {
  const doctorUserId = `doctor_${doctorId}`;
  const connection = wsConnections.get(doctorUserId);

  if (connection && connection.readyState === 1) { // WebSocket.OPEN
    connection.send(JSON.stringify(notification));
    return true;
  }
  return false;
}
