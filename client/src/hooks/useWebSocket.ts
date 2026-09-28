import { useEffect, useRef, useState } from 'react';

interface NotificationData {
  type: string;
  appointmentId: number;
  patientName: string;
  appointmentTime: string;
  appointmentDate: string;
  message: string;
}

interface UseWebSocketProps {
  userId: string;
  onNotification?: (notification: NotificationData) => void;
}

export function useWebSocket({ userId, onNotification }: UseWebSocketProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);

  const connect = () => {
    try {
      // Get the WebSocket URL - use same host as current page but with ws/wss protocol
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      let wsHost = window.location.host;
      
      // In development, ensure we have the correct port
      if (!wsHost.includes(':') && window.location.hostname === 'localhost') {
        wsHost = 'localhost:5000';
      } else if (wsHost.includes(':undefined')) {
        wsHost = wsHost.replace(':undefined', ':5000');
      }
      
      const wsUrl = `${wsProtocol}//${wsHost}/ws`;
      console.log('WebSocket connecting to:', wsUrl);
      
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
        
        // Authenticate with the server
        if (ws.current) {
          ws.current.send(JSON.stringify({
            type: 'auth',
            userId: userId
          }));
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'auth_success') {
            console.log('WebSocket authentication successful');
          } else if ((data.type === 'patient_arrived' || data.type === 'appointment_added') && onNotification) {
            onNotification(data);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        
        // Attempt to reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(() => {
          console.log('Attempting to reconnect WebSocket...');
          connect();
        }, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('WebSocket connection error');
      };

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setError('Failed to create WebSocket connection');
    }
  };

  const disconnect = () => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
    
    setIsConnected(false);
  };

  useEffect(() => {
    if (userId) {
      console.log('useWebSocket: Initializing WebSocket for user:', userId);
      connect();
    } else {
      console.log('useWebSocket: No userId provided, skipping WebSocket connection');
    }
    
    return () => {
      disconnect();
    };
  }, [userId]);

  return {
    isConnected,
    error,
    disconnect
  };
}