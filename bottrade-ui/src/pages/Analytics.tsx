import React from 'react'

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Analytics</h1>
        <p className="text-gray-400">Performance analysis & statistics</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="text-gray-400 text-sm mb-1">Total P&L</div>
          <div className="text-3xl font-bold text-green-400">+1,245,000 VND</div>
          <div className="text-xs text-gray-500 mt-1">+2.5% Return</div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="text-gray-400 text-sm mb-1">Win Rate</div>
          <div className="text-3xl font-bold text-blue-400">72%</div>
          <div className="text-xs text-gray-500 mt-1">36 wins / 50 trades</div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="text-gray-400 text-sm mb-1">Profit Factor</div>
          <div className="text-3xl font-bold text-yellow-400">2.45x</div>
          <div className="text-xs text-gray-500 mt-1">Gains / Losses ratio</div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="text-gray-400 text-sm mb-1">Max Drawdown</div>
          <div className="text-3xl font-bold text-red-400">-8.2%</div>
          <div className="text-xs text-gray-500 mt-1">Largest loss period</div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-bold text-white mb-4">Equity Curve</h3>
          <div className="bg-black rounded h-64 flex items-center justify-center text-gray-400">
            Chart placeholder (Recharts)
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-bold text-white mb-4">Monthly Return</h3>
          <div className="bg-black rounded h-64 flex items-center justify-center text-gray-400">
            Chart placeholder (Recharts)
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
                <td className="py-3 px-3 text-right font-bold text-white">50</td>
              </tr>
              <tr className="border-b border-gray-700">
                <td className="py-3 px-3 text-gray-400">Winning Trades</td>
                <td className="py-3 px-3 text-right font-bold text-green-400">36</td>
              </tr>
              <tr className="border-b border-gray-700">
                <td className="py-3 px-3 text-gray-400">Losing Trades</td>
                <td className="py-3 px-3 text-right font-bold text-red-400">14</td>
              </tr>
              <tr className="border-b border-gray-700">
                <td className="py-3 px-3 text-gray-400">Consecutive Wins</td>
                <td className="py-3 px-3 text-right font-bold text-white">8</td>
              </tr>
              <tr className="border-b border-gray-700">
                <td className="py-3 px-3 text-gray-400">Best Trade</td>
                <td className="py-3 px-3 text-right font-bold text-green-400">+285,000 VND</td>
              </tr>
              <tr className="border-b border-gray-700">
                <td className="py-3 px-3 text-gray-400">Worst Trade</td>
                <td className="py-3 px-3 text-right font-bold text-red-400">-45,000 VND</td>
              </tr>
              <tr className="border-b border-gray-700">
                <td className="py-3 px-3 text-gray-400">Average Trade</td>
                <td className="py-3 px-3 text-right font-bold text-white">+24,900 VND</td>
              </tr>
              <tr>
                <td className="py-3 px-3 text-gray-400">Sharpe Ratio</td>
                <td className="py-3 px-3 text-right font-bold text-white">1.45</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
