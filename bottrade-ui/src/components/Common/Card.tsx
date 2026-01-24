import React from 'react'

interface CardProps {
  title?: string
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
  const colsMap: Record<number, string> = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
  }
  
  return (
    <div className={`grid ${colsMap[cols] || colsMap[3]} gap-4`}>
      {children}
    </div>
  )
}
