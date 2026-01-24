import React from 'react'
import Header from './Header'
import Sidebar from './Sidebar'
import useAppStore from '../../store/appStore'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { theme } = useAppStore()

  return (
    <div className={theme === 'dark' ? 'dark' : ''}>
      <div className="bg-gray-950 text-gray-100 min-h-screen">
        <Header />
        <div className="flex">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            <div className="p-6">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
