import React, { useEffect, useState, useMemo } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { RefreshCw } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import type { Signal } from '../types/api'

interface Stats {
  totalTrades: number
  wins: number
  losses: number
  totalPnL: number
  winRate: number
  avgWin: number
  avgLoss: number
  profitFactor: number
  maxConsecutiveWins: number
  bestTrade: number
  worstTrade: number
  avgTrade: number
}

export default function AnalyticsPage() {
  const { get } = useApi()
  const { signals, setSignals } = useAppStore()
  const [loading, setLoading] = useState(true)

  // Fetch signals data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await get('/api/v1/signals?limit=500')
        if (response.data) {
          setSignals(response.data)
        }
      } catch (error) {
        console.error('Failed to fetch signals:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // Calculate statistics from closed signals
  const stats = useMemo<Stats>(() => {
    const closedSignals = signals.filter(s => s.status === 'CLOSED' && s.pnl !== undefined)
    
    if (closedSignals.length === 0) {
      return {
        totalTrades: 0, wins: 0, losses: 0, totalPnL: 0, winRate: 0,
        avgWin: 0, avgLoss: 0, profitFactor: 0, maxConsecutiveWins: 0,
        bestTrade: 0, worstTrade: 0, avgTrade: 0
      }
    }

    const wins = closedSignals.filter(s => (s.pnl || 0) > 0)
    const losses = closedSignals.filter(s => (s.pnl || 0) < 0)
    const totalPnL = closedSignals.reduce((sum, s) => sum + (s.pnl || 0), 0)
    const totalWinAmount = wins.reduce((sum, s) => sum + (s.pnl || 0), 0)
    const totalLossAmount = Math.abs(losses.reduce((sum, s) => sum + (s.pnl || 0), 0))

    // Calculate max consecutive wins
    let maxConsecWins = 0
    let currentConsec = 0
    closedSignals.forEach(s => {
      if ((s.pnl || 0) > 0) {
        currentConsec++
        maxConsecWins = Math.max(maxConsecWins, currentConsec)
      } else {
        currentConsec = 0
      }
    })

    return {
      totalTrades: closedSignals.length,
      wins: wins.length,
      losses: losses.length,
      totalPnL,
      winRate: closedSignals.length > 0 ? (wins.length / closedSignals.length) * 100 : 0,
      avgWin: wins.length > 0 ? totalWinAmount / wins.length : 0,
      avgLoss: losses.length > 0 ? totalLossAmount / losses.length : 0,
      profitFactor: totalLossAmount > 0 ? totalWinAmount / totalLossAmount : totalWinAmount > 0 ? Infinity : 0,
      maxConsecutiveWins: maxConsecWins,
      bestTrade: closedSignals.length > 0 ? Math.max(...closedSignals.map(s => s.pnl || 0)) : 0,
      worstTrade: closedSignals.length > 0 ? Math.min(...closedSignals.map(s => s.pnl || 0)) : 0,
      avgTrade: closedSignals.length > 0 ? totalPnL / closedSignals.length : 0
    }
  }, [signals])

  // Generate equity curve data
  const equityCurve = useMemo(() => {
    const closedSignals = signals
      .filter(s => s.status === 'CLOSED' && s.pnl !== undefined)
      .sort((a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime())
    
    let cumulative = 0
    return closedSignals.map((s, idx) => {
      cumulative += s.pnl || 0
      return {
        trade: idx + 1,
        equity: cumulative,
        date: s.created_at ? new Date(s.created_at).toLocaleDateString('vi-VN') : ''
      }
    })
  }, [signals])

  // Generate monthly return data
  const monthlyReturn = useMemo(() => {
    const closedSignals = signals.filter(s => s.status === 'CLOSED' && s.pnl !== undefined)
    const monthlyData = new Map<string, number>()
    
    closedSignals.forEach(s => {
      if (s.created_at) {
        const date = new Date(s.created_at)
        const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
        monthlyData.set(key, (monthlyData.get(key) || 0) + (s.pnl || 0))
      }
    })

    return Array.from(monthlyData.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([month, pnl]) => ({ month, pnl }))
  }, [signals])

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('vi-VN').format(Math.round(value)) + ' VND'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Analytics</h1>
          <p className="text-gray-400">Performance analysis & statistics</p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="p-2 hover:bg-gray-800 rounded transition"
          title="Refresh"
        >
          <RefreshCw className={`w-5 h-5 text-gray-300 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading analytics...</div>
      ) : (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <div className="text-gray-400 text-sm mb-1">Total P&L</div>
              <div className={`text-3xl font-bold ${stats.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.totalPnL >= 0 ? '+' : ''}{formatCurrency(stats.totalPnL)}
              </div>
              <div className="text-xs text-gray-500 mt-1">{stats.totalTrades} trades</div>
            </div>

            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <div className="text-gray-400 text-sm mb-1">Win Rate</div>
              <div className="text-3xl font-bold text-blue-400">{stats.winRate.toFixed(1)}%</div>
              <div className="text-xs text-gray-500 mt-1">{stats.wins} wins / {stats.totalTrades} trades</div>
            </div>

            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <div className="text-gray-400 text-sm mb-1">Profit Factor</div>
              <div className="text-3xl font-bold text-yellow-400">
                {stats.profitFactor === Infinity ? '∞' : stats.profitFactor.toFixed(2)}x
              </div>
              <div className="text-xs text-gray-500 mt-1">Gains / Losses ratio</div>
            </div>

            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <div className="text-gray-400 text-sm mb-1">Avg Win / Loss</div>
              <div className="text-3xl font-bold text-white">
                {stats.avgLoss > 0 ? (stats.avgWin / stats.avgLoss).toFixed(2) : '∞'}x
              </div>
              <div className="text-xs text-gray-500 mt-1">Risk/Reward ratio</div>
            </div>
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-bold text-white mb-4">Equity Curve</h3>
              <div className="h-64">
                {equityCurve.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={equityCurve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="trade" stroke="#9ca3af" fontSize={12} />
                      <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                        labelStyle={{ color: '#fff' }}
                        formatter={(value: number) => [formatCurrency(value), 'Equity']}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="equity" 
                        stroke="#22c55e" 
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400">
                    No closed trades yet
                  </div>
                )}
              </div>
            </div>

            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h3 className="text-lg font-bold text-white mb-4">Monthly Return</h3>
              <div className="h-64">
                {monthlyReturn.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={monthlyReturn}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="month" stroke="#9ca3af" fontSize={12} />
                      <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                        labelStyle={{ color: '#fff' }}
                        formatter={(value: number) => [formatCurrency(value), 'P&L']}
                      />
                      <Bar dataKey="pnl">
                        {monthlyReturn.map((entry, idx) => (
                          <Cell key={idx} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400">
                    No monthly data yet
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Detailed Statistics Table */}
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h3 className="text-lg font-bold text-white mb-4">Detailed Statistics</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Total Trades</td>
                    <td className="py-3 px-3 text-right font-bold text-white">{stats.totalTrades}</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Winning Trades</td>
                    <td className="py-3 px-3 text-right font-bold text-green-400">{stats.wins}</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Losing Trades</td>
                    <td className="py-3 px-3 text-right font-bold text-red-400">{stats.losses}</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Max Consecutive Wins</td>
                    <td className="py-3 px-3 text-right font-bold text-white">{stats.maxConsecutiveWins}</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Best Trade</td>
                    <td className="py-3 px-3 text-right font-bold text-green-400">+{formatCurrency(stats.bestTrade)}</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Worst Trade</td>
                    <td className="py-3 px-3 text-right font-bold text-red-400">{formatCurrency(stats.worstTrade)}</td>
                  </tr>
                  <tr className="border-b border-gray-700">
                    <td className="py-3 px-3 text-gray-400">Average Trade</td>
                    <td className={`py-3 px-3 text-right font-bold ${stats.avgTrade >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {stats.avgTrade >= 0 ? '+' : ''}{formatCurrency(stats.avgTrade)}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-3 text-gray-400">Avg Win</td>
                    <td className="py-3 px-3 text-right font-bold text-green-400">+{formatCurrency(stats.avgWin)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
