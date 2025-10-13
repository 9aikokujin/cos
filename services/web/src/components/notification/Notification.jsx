import { useEffect } from "react";

import { useNotificationStore } from "@/app/store/notification/store";

export const Notification = () => {
  const { notification, clearNotification } = useNotificationStore();

  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => clearNotification(), 3000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  if (!notification) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "20px",
        right: "20px",
        backgroundColor: notification.type === "error" ? "#f87171" : "#34d399",
        color: "white",
        padding: "10px 16px",
        borderRadius: "8px",
        boxShadow: "0 4px 10px rgba(0,0,0,0.1)",
      }}
    >
      {notification.message}
    </div>
  );
};
