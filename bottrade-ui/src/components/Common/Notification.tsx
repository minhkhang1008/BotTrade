import React, { useState } from 'react'
import { AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react'

export type NotificationType = 'success' | 'error' | 'warning' | 'info'

interface NotificationProps {
  id: string
  type: NotificationType
  title: string
  message: string
  onClose: () => void
  duration?: number
}

export function Notification({ id, type, title, message, onClose, duration = 5000 }: NotificationProps) {
  React.useEffect(() => {
    if (duration) {
      const timer = setTimeout(onClose, duration)
      return () => clearTimeout(timer)
    }
  }, [duration, onClose])

  const icons = {
    success: <CheckCircle className="w-5 h-5 text-green-400" />,
    error: <AlertCircle className="w-5 h-5 text-red-400" />,
    warning: <AlertTriangle className="w-5 h-5 text-yellow-400" />,
    info: <Info className="w-5 h-5 text-blue-400" />
  }

  const bgColors = {
    success: 'bg-green-900/30 border-green-700',
    error: 'bg-red-900/30 border-red-700',
    warning: 'bg-yellow-900/30 border-yellow-700',
    info: 'bg-blue-900/30 border-blue-700'
  }

  return (
    <div className={`rounded-lg border p-4 flex items-start gap-3 ${bgColors[type]} animate-in fade-in slide-in-from-top-2`}>
      {icons[type]}
      <div className="flex-1">
        <h4 className="font-bold text-white">{title}</h4>
        <p className="text-sm text-gray-300">{message}</p>
      </div>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-gray-200 transition"
      >
        ✕
      </button>
    </div>
  )
}

export function useNotification() {
  const [notifications, setNotifications] = useState<NotificationProps[]>([])

  const add = (type: NotificationType, title: string, message: string, duration?: number) => {
    const id = Math.random().toString(36).substr(2, 9)
    const notification = { id, type, title, message, onClose: () => remove(id), duration }
    setNotifications(prev => [...prev, notification as NotificationProps])
  }

  const remove = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  return { notifications, add, remove }
}
