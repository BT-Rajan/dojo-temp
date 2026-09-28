import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bell, X, User, Clock, Calendar, CalendarPlus } from 'lucide-react';
import { format, parseISO } from 'date-fns';

interface NotificationData {
  type: string;
  appointmentId: number;
  patientName: string;
  appointmentTime: string;
  appointmentDate: string;
  message: string;
}

interface PatientArrivalNotificationProps {
  notification: NotificationData | null;
  onDismiss: () => void;
}

export function PatientArrivalNotification({ notification, onDismiss }: PatientArrivalNotificationProps) {
  const [isVisible, setIsVisible] = useState(false);

  const playNotificationSound = (isNewAppt = false) => {
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      if (isNewAppt) {
        // Three rising tones for new appointment
        oscillator.frequency.setValueAtTime(600, audioContext.currentTime);
        oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.12);
        oscillator.frequency.setValueAtTime(1000, audioContext.currentTime + 0.24);
        gainNode.gain.setValueAtTime(0.08, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0, audioContext.currentTime + 0.4);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.4);
      } else {
        // Two beeps for patient arrival (existing behaviour)
        oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
        oscillator.frequency.setValueAtTime(1000, audioContext.currentTime + 0.1);
        oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.2);
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0, audioContext.currentTime + 0.3);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
      }
    } catch {
      // Sound not critical
    }
  };

  useEffect(() => {
    if (notification) {
      setIsVisible(true);
      playNotificationSound(notification.type === 'appointment_added');

      const timer = setTimeout(() => {
        handleDismiss();
      }, 12000);

      return () => clearTimeout(timer);
    } else {
      setIsVisible(false);
    }
  }, [notification]);

  const handleDismiss = () => {
    setIsVisible(false);
    setTimeout(() => onDismiss(), 300);
  };

  if (!notification || !isVisible) return null;

  const isNewAppt = notification.type === 'appointment_added';

  const formatDate = (d: string) => {
    try { return format(parseISO(d), 'MMM dd, yyyy'); } catch { return d; }
  };

  const formatTime = (t: string) => {
    try {
      const [h, m] = t.split(':');
      const d = new Date();
      d.setHours(parseInt(h), parseInt(m));
      return format(d, 'h:mm a');
    } catch { return t; }
  };

  return (
    <div
      className={`fixed top-4 right-4 z-50 transition-all duration-300 ${
        isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-full'
      }`}
      data-testid="notification-patient-arrival"
    >
      <Card className={`w-80 bg-white shadow-xl border-2 ${isNewAppt ? 'border-blue-500' : 'border-green-500'}`}>
        <div className="p-4">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center space-x-2">
              <div className={`p-2 rounded-full ${isNewAppt ? 'bg-blue-100' : 'bg-green-100'}`}>
                {isNewAppt
                  ? <CalendarPlus className="w-5 h-5 text-blue-600 animate-bounce" />
                  : <Bell className="w-5 h-5 text-green-600 animate-bounce" />
                }
              </div>
              <h3 className={`font-semibold ${isNewAppt ? 'text-blue-800' : 'text-green-800'}`}>
                {isNewAppt ? 'New Patient Scheduled' : 'Patient Arrived'}
              </h3>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDismiss}
              className="h-6 w-6 p-0 hover:bg-gray-100"
              data-testid="button-dismiss-notification"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* Details */}
          <div className="space-y-2">
            <div className="flex items-center space-x-2 text-sm">
              <User className="w-4 h-4 text-gray-500" />
              <span className="font-medium" data-testid="text-patient-name">
                {notification.patientName}
              </span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Calendar className="w-4 h-4" />
              <span data-testid="text-appointment-date">{formatDate(notification.appointmentDate)}</span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <Clock className="w-4 h-4" />
              <span data-testid="text-appointment-time">{formatTime(notification.appointmentTime)}</span>
            </div>
          </div>

          {/* Message */}
          <div className={`mt-3 p-2 rounded text-sm ${isNewAppt ? 'bg-blue-50' : 'bg-gray-50'}`}>
            <p className={`${isNewAppt ? 'text-blue-700' : 'text-gray-700'}`} data-testid="text-notification-message">
              {notification.message}
            </p>
          </div>

          <div className="mt-3">
            <Button
              size="sm"
              onClick={handleDismiss}
              className={`w-full ${isNewAppt ? 'bg-blue-600 hover:bg-blue-700' : ''}`}
              data-testid="button-acknowledge"
            >
              Acknowledge
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
