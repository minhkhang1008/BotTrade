import React from 'react'

interface CardProps {
  title: string
  children: React.ReactNode
  className?: string
}

export function Card({ title, children, className = '' }: CardProps) {
  return (
    <div className={`bg-gray-800 rounded-lg border border-gray-700 p-4 ${className}`}>
      {title && <h3 className="text-lg font-bold text-white mb-4">{title}</h3>}
      {children}
    </div>
  )
}

export function CardGrid({ children, cols = 3 }: { children: React.ReactNode; cols?: number }) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-${cols} gap-4`}>
      {children}
    </div>
  )
}
