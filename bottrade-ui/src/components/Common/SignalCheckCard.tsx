import React from 'react'
import { 
  CheckCircle, XCircle, Activity, TrendingUp, Target, 
  BarChart3, Zap, ArrowUpRight, ArrowDownRight, Layers,
  CircleDot, Gauge, Timer
} from 'lucide-react'
import useAppStore from '../../store/appStore'
import type { SignalCheck } from '../../types/api'

// Progress ring component for visual indicators
function ProgressRing({ 
  value, 
  max, 
  size = 48, 
  strokeWidth = 4,
  color = 'blue',
  label 
}: { 
  value: number
  max: number
  size?: number
  strokeWidth?: number
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple'
  label: string
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const progress = Math.min(value / max, 1)
  const offset = circumference - progress * circumference
  
  const colorClasses = {
    blue: 'stroke-blue-500',
    green: 'stroke-green-500',
    yellow: 'stroke-yellow-500',
    red: 'stroke-red-500',
    purple: 'stroke-purple-500'
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="transform -rotate-90" width={size} height={size}>
          <circle
            className="stroke-gray-700"
            fill="transparent"
            strokeWidth={strokeWidth}
            r={radius}
            cx={size / 2}
            cy={size / 2}
          />
          <circle
            className={`${colorClasses[color]} transition-all duration-500`}
            fill="transparent"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            r={radius}
            cx={size / 2}
            cy={size / 2}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xs font-bold text-white">{value}/{max}</span>
        </div>
      </div>
      <span className="text-xs text-gray-400">{label}</span>
    </div>
  )
}

// Condition card with detailed analysis
function ConditionCard({ 
  title, 
  passed, 
  icon: Icon,
  children 
}: { 
  title: string
  passed: boolean
  icon: React.ElementType
  children?: React.ReactNode
}) {
  return (
    <div className={`rounded-lg p-3 transition-all duration-300 ${
      passed 
        ? 'bg-green-900/30 border border-green-600/50' 
        : 'bg-gray-800/50 border border-gray-600/30'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        {passed ? (
          <CheckCircle className="w-4 h-4 text-green-400" />
        ) : (
          <XCircle className="w-4 h-4 text-gray-500" />
        )}
        <Icon className={`w-4 h-4 ${passed ? 'text-green-400' : 'text-gray-500'}`} />
        <span className={`text-sm font-medium ${passed ? 'text-green-300' : 'text-gray-400'}`}>
          {title}
        </span>
      </div>
      {children && (
        <div className="ml-6 text-xs text-gray-300">
          {children}
        </div>
      )}
    </div>
  )
}

// RSI Gauge visualization
function RSIGauge({ value }: { value: number }) {
  const percentage = Math.min(Math.max(value, 0), 100)
  const isGood = value >= 50
  
  return (
    <div className="bg-gray-900/70 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Gauge className="w-4 h-4 text-purple-400" />
          <span className="text-xs text-gray-400">RSI</span>
        </div>
        <span className={`text-sm font-mono font-bold ${
          isGood ? 'text-green-400' : 'text-gray-400'
        }`}>
          {value.toFixed(1)}
        </span>
      </div>
      <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
        {/* Zones */}
        <div className="absolute inset-0 flex">
          <div className="w-[30%] bg-red-900/50" />
          <div className="w-[40%] bg-gray-600/50" />
          <div className="w-[30%] bg-green-900/50" />
        </div>
        {/* Indicator */}
        <div 
          className="absolute top-0 bottom-0 w-1 bg-white rounded-full shadow-lg transition-all duration-300"
          style={{ left: `calc(${percentage}% - 2px)` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-gray-500">
        <span>Oversold</span>
        <span>50 {isGood ? '✓' : ''}</span>
        <span>Overbought</span>
      </div>
    </div>
  )
}

// MACD Visualization
function MACDIndicator({ macd, signal }: { macd: number; signal: number }) {
  const isBullish = macd > signal
  const histogram = macd - signal
  
  return (
    <div className="bg-gray-900/70 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <TrendingUp className="w-4 h-4 text-blue-400" />
          <span className="text-xs text-gray-400">MACD</span>
        </div>
        <div className={`flex items-center gap-1 ${isBullish ? 'text-green-400' : 'text-red-400'}`}>
          {isBullish ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          <span className="text-xs font-medium">{isBullish ? 'Bullish' : 'Bearish'}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex justify-between">
          <span className="text-blue-400">MACD:</span>
          <span className="font-mono text-white">{macd.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-orange-400">Signal:</span>
          <span className="font-mono text-white">{signal.toFixed(2)}</span>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs text-gray-500">Histogram:</span>
        <div className="flex-1 h-3 bg-gray-700 rounded relative">
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-500" />
          <div 
            className={`absolute top-0 bottom-0 rounded transition-all duration-300 ${
              histogram >= 0 ? 'bg-green-500 left-1/2' : 'bg-red-500 right-1/2'
            }`}
            style={{ 
              width: `${Math.min(Math.abs(histogram) * 10, 50)}%`
            }}
          />
        </div>
        <span className={`text-xs font-mono ${histogram >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {histogram >= 0 ? '+' : ''}{histogram.toFixed(2)}
        </span>
      </div>
    </div>
  )
}

// Support Zone Visualization
function SupportZoneVisual({ 
  zoneHigh, 
  zoneLow, 
  barLow, 
  barHigh,
  pivotPrice 
}: { 
  zoneHigh: number
  zoneLow: number
  barLow: number
  barHigh: number
  pivotPrice: number
}) {
  const inZone = barLow >= zoneLow && barLow <= zoneHigh
  
  return (
    <div className="bg-gray-900/70 rounded-lg p-3">
      <div className="flex items-center gap-1.5 mb-2">
        <Layers className="w-4 h-4 text-cyan-400" />
        <span className="text-xs text-gray-400">Support Zone Check</span>
        {inZone && <CheckCircle className="w-3 h-3 text-green-400" />}
      </div>
      
      <div className="relative h-16 bg-gray-800 rounded overflow-hidden">
        {/* Support Zone Band */}
        <div 
          className="absolute left-0 right-0 bg-green-900/40 border-t border-b border-green-600/50"
          style={{ 
            top: '30%', 
            bottom: '30%',
          }}
        >
          <div className="absolute -top-4 left-1 text-[10px] text-green-400">
            Zone High: {zoneHigh.toLocaleString()}
          </div>
          <div className="absolute -bottom-4 left-1 text-[10px] text-green-400">
            Zone Low: {zoneLow.toLocaleString()}
          </div>
        </div>
        
        {/* Pivot Point */}
        <div 
          className="absolute left-0 right-0 h-px bg-cyan-500/70"
          style={{ top: '50%' }}
        >
          <div className="absolute right-1 -top-3 text-[10px] text-cyan-400 flex items-center gap-1">
            <CircleDot className="w-2 h-2" />
            Pivot: {pivotPrice.toLocaleString()}
          </div>
        </div>
        
        {/* Bar Low indicator */}
        <div 
          className={`absolute left-1/2 transform -translate-x-1/2 w-8 h-1 rounded ${
            inZone ? 'bg-green-500' : 'bg-red-500'
          }`}
          style={{ 
            top: inZone ? '50%' : '10%',
          }}
        />
      </div>
      
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-gray-400">Bar Low:</span>
        <span className={`font-mono ${inZone ? 'text-green-400' : 'text-red-400'}`}>
          {barLow.toLocaleString()}
        </span>
        <span className={`px-2 py-0.5 rounded text-[10px] ${
          inZone 
            ? 'bg-green-900/50 text-green-400' 
            : 'bg-red-900/50 text-red-400'
        }`}>
          {inZone ? '✓ In Zone' : '✗ Outside Zone'}
        </span>
      </div>
    </div>
  )
}

interface SignalCheckItemProps {
  check: SignalCheck
}

function SignalCheckItem({ check }: SignalCheckItemProps) {
  const progress = (check.conditions_passed / check.total_conditions) * 100
  const isClose = check.conditions_passed >= 3
  const isTriggered = check.conditions_passed === check.total_conditions
  
  // Parse conditions to determine which ones passed
  const hasUptrend = check.passed.some(c => c.toLowerCase().includes('uptrend'))
  const hasSupport = check.passed.some(c => c.toLowerCase().includes('support'))
  const hasPattern = check.passed.some(c => c.toLowerCase().includes('pattern') || c.toLowerCase().includes('hammer') || c.toLowerCase().includes('engulfing'))
  const hasRSI = check.passed.some(c => c.toLowerCase().includes('rsi') || c.toLowerCase().includes('macd'))
  
  // Get pivot counts from analysis
  const pivotLowsCount = check.analysis?.pivot_lows_count || 0
  const pivotHighsCount = check.analysis?.pivot_highs_count || 0
  
  // Get trend analysis results (consecutive higher pairs)
  const higherLowsCount = check.analysis?.higher_lows_count || 0
  const higherHighsCount = check.analysis?.higher_highs_count || 0
  const isUptrend = check.analysis?.is_uptrend || false
  
  // If signal is triggered, show Active Signal card instead
  if (isTriggered) {
    return (
      <div className="bg-gradient-to-br from-green-900/80 to-emerald-900/80 rounded-xl p-5 border-2 border-green-400 shadow-xl shadow-green-500/30 animate-pulse">
        {/* Active Signal Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center animate-bounce">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-white">{check.symbol}</span>
                <span className="px-3 py-1 bg-green-500 text-white text-sm font-bold rounded-full">
                  🎯 ACTIVE SIGNAL
                </span>
              </div>
              <span className="text-green-300 text-sm">BUY Signal Generated!</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-green-400">4/4</div>
            <div className="text-xs text-green-300">All conditions met</div>
          </div>
        </div>

        {/* All 4 Conditions Passed */}
        <div className="grid grid-cols-4 gap-2 mb-4">
          <div className="bg-green-800/50 rounded-lg p-2 text-center border border-green-500/50">
            <CheckCircle className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <div className="text-xs text-green-300 font-medium">Uptrend</div>
            <div className="text-[10px] text-green-400">✓ PASS</div>
          </div>
          <div className="bg-green-800/50 rounded-lg p-2 text-center border border-green-500/50">
            <CheckCircle className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <div className="text-xs text-green-300 font-medium">Support</div>
            <div className="text-[10px] text-green-400">✓ PASS</div>
          </div>
          <div className="bg-green-800/50 rounded-lg p-2 text-center border border-green-500/50">
            <CheckCircle className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <div className="text-xs text-green-300 font-medium">Pattern</div>
            <div className="text-[10px] text-green-400">✓ PASS</div>
          </div>
          <div className="bg-green-800/50 rounded-lg p-2 text-center border border-green-500/50">
            <CheckCircle className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <div className="text-xs text-green-300 font-medium">Momentum</div>
            <div className="text-[10px] text-green-400">✓ PASS</div>
          </div>
        </div>

        {/* Price Info */}
        <div className="grid grid-cols-4 gap-2 text-center">
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-[10px] text-gray-400">Open</div>
            <div className="text-sm font-mono text-white">{check.bar.open?.toLocaleString()}</div>
          </div>
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-[10px] text-gray-400">High</div>
            <div className="text-sm font-mono text-green-400">{check.bar.high?.toLocaleString()}</div>
          </div>
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-[10px] text-gray-400">Low</div>
            <div className="text-sm font-mono text-red-400">{check.bar.low?.toLocaleString()}</div>
          </div>
          <div className="bg-black/30 rounded-lg p-2">
            <div className="text-[10px] text-gray-400">Close</div>
            <div className="text-sm font-mono text-white">{check.bar.close?.toLocaleString()}</div>
          </div>
        </div>
        
        <div className="mt-4 text-center text-green-300 text-sm">
          ⏰ {new Date(check.timestamp).toLocaleTimeString()}
        </div>
      </div>
    )
  }
  
  // Normal checking state - show conditions table
  return (
    <div className={`bg-gray-800/50 rounded-xl p-4 border-2 transition-all duration-500 ${
      isClose 
        ? 'border-yellow-500/50 shadow-lg shadow-yellow-500/10' 
        : 'border-gray-700'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
            isTriggered ? 'bg-green-500' : 'bg-blue-600'
          }`}>
            {isTriggered ? (
              <Zap className="w-5 h-5 text-white" />
            ) : (
              <Activity className="w-5 h-5 text-white animate-pulse" />
            )}
          </div>
          <div>
            <span className="font-bold text-white text-xl">{check.symbol}</span>
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Timer className="w-3 h-3" />
              {new Date(check.timestamp).toLocaleTimeString()}
            </div>
          </div>
        </div>
        
        <div className="text-right">
          <div className={`text-2xl font-bold ${
            isTriggered ? 'text-green-400' : isClose ? 'text-yellow-400' : 'text-blue-400'
          }`}>
            {check.conditions_passed}/{check.total_conditions}
          </div>
          <div className="text-xs text-gray-500">conditions met</div>
        </div>
      </div>

      {/* Main Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Signal Progress</span>
          <span>{progress.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              isTriggered 
                ? 'bg-gradient-to-r from-green-600 to-green-400' 
                : isClose 
                  ? 'bg-gradient-to-r from-yellow-600 to-yellow-400' 
                  : 'bg-gradient-to-r from-blue-600 to-blue-400'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Analysis Details with Pivots */}
      {check.analysis && (
        <div className="mb-4 p-3 bg-gray-900/50 rounded-lg">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-white">Trend Analysis</span>
            {isUptrend ? (
              <span className="text-xs px-2 py-0.5 bg-green-900/50 text-green-400 rounded">
                ✓ Uptrend
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 bg-gray-700 text-gray-400 rounded">
                No Uptrend
              </span>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <ProgressRing 
              value={higherLowsCount} 
              max={3} 
              color={higherLowsCount >= 3 ? 'green' : 'blue'}
              label="Higher Lows"
            />
            <ProgressRing 
              value={higherHighsCount} 
              max={3} 
              color={higherHighsCount >= 3 ? 'green' : 'blue'}
              label="Higher Highs"
            />
          </div>
          
          <div className="mt-2 text-xs text-gray-500 text-center">
            Need 3/3 consecutive pairs for uptrend • Using last 8 pivots
          </div>
          
          {check.analysis.pivot_lows.length > 0 && (
            <div className="mt-3 text-xs">
              <span className="text-gray-500">Recent Pivot Lows: </span>
              <span className="text-green-400 font-mono">
                {check.analysis.pivot_lows.slice(-4).map(p => p.price.toLocaleString()).join(' → ')}
              </span>
            </div>
          )}
          
          {check.analysis.pivot_highs.length > 0 && (
            <div className="mt-1 text-xs">
              <span className="text-gray-500">Recent Pivot Highs: </span>
              <span className="text-blue-400 font-mono">
                {check.analysis.pivot_highs.slice(-4).map(p => p.price.toLocaleString()).join(' → ')}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Support Zone */}
      {check.analysis?.support_zone && (
        <div className="mb-4">
          <SupportZoneVisual
            zoneHigh={check.analysis.support_zone.zone_high}
            zoneLow={check.analysis.support_zone.zone_low}
            barLow={check.analysis.bar_low}
            barHigh={check.analysis.bar_high}
            pivotPrice={check.analysis.support_zone.pivot_price}
          />
        </div>
      )}

      {/* Indicators Row */}
      {check.indicators && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          {check.indicators.rsi !== undefined && check.indicators.rsi !== null && (
            <RSIGauge value={check.indicators.rsi} />
          )}
          {check.indicators.macd !== undefined && check.indicators.macd !== null && 
           check.indicators.macd_signal !== undefined && check.indicators.macd_signal !== null && (
            <MACDIndicator 
              macd={check.indicators.macd} 
              signal={check.indicators.macd_signal} 
            />
          )}
        </div>
      )}

      {/* Bar OHLC */}
      <div className="grid grid-cols-4 gap-2 mb-4 text-center">
        <div className="bg-gray-900/50 rounded-lg p-2">
          <div className="text-[10px] text-gray-500 uppercase">Open</div>
          <div className="text-sm font-mono text-white">{check.bar.open?.toLocaleString()}</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-2">
          <div className="text-[10px] text-gray-500 uppercase">High</div>
          <div className="text-sm font-mono text-green-400">{check.bar.high?.toLocaleString()}</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-2">
          <div className="text-[10px] text-gray-500 uppercase">Low</div>
          <div className="text-sm font-mono text-red-400">{check.bar.low?.toLocaleString()}</div>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-2">
          <div className="text-[10px] text-gray-500 uppercase">Close</div>
          <div className="text-sm font-mono text-white">{check.bar.close?.toLocaleString()}</div>
        </div>
      </div>

      {/* Condition Cards */}
      <div className="grid grid-cols-2 gap-2">
        <ConditionCard title="Uptrend" passed={hasUptrend} icon={TrendingUp}>
          {hasUptrend 
            ? '✓ 3/3 Higher Lows & Highs' 
            : `HL: ${higherLowsCount}/3 | HH: ${higherHighsCount}/3`}
        </ConditionCard>
        <ConditionCard title="Support Zone" passed={hasSupport} icon={Target}>
          {hasSupport 
            ? '✓ Price touched support' 
            : check.analysis?.support_zone 
              ? `Zone: ${check.analysis.support_zone.zone_low.toLocaleString()}-${check.analysis.support_zone.zone_high.toLocaleString()}`
              : 'Waiting for zone touch'}
        </ConditionCard>
        <ConditionCard title="Pattern" passed={hasPattern} icon={BarChart3}>
          {hasPattern 
            ? '✓ Bullish pattern detected' 
            : 'Scanning for Hammer/Engulfing...'}
        </ConditionCard>
        <ConditionCard title="Momentum" passed={hasRSI} icon={Gauge}>
          {hasRSI 
            ? '✓ RSI/MACD confirmed' 
            : check.indicators?.rsi 
              ? `RSI: ${check.indicators.rsi.toFixed(1)} (need >50)`
              : 'Checking momentum...'}
        </ConditionCard>
      </div>

      {/* Progress Summary */}
      <div className={`mt-4 p-3 rounded-lg text-center ${
        isClose 
          ? 'bg-yellow-900/30 border border-yellow-500/30' 
          : 'bg-gray-900/50'
      }`}>
        <span className={`text-sm ${isClose ? 'text-yellow-300' : 'text-gray-400'}`}>
          {isClose 
            ? `⚡ Almost there! ${4 - check.conditions_passed} more condition${4 - check.conditions_passed > 1 ? 's' : ''} needed`
            : `📊 Checking conditions... ${check.conditions_passed}/4 passed`}
        </span>
      </div>
    </div>
  )
}

export default function SignalCheckCard() {
  const signalChecks = useAppStore(state => state.signalChecks)
  
  // Convert Map to array and sort by symbol alphabetically (fixed position)
  // This ensures symbols stay in the same position and don't jump around
  const checksArray = Array.from(signalChecks.values()).sort((a, b) => 
    a.symbol.localeCompare(b.symbol)
  )

  if (checksArray.length === 0) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-blue-600/30 flex items-center justify-center">
            <Activity className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Signal Analysis</h3>
            <p className="text-xs text-gray-500">Real-time condition monitoring</p>
          </div>
        </div>
        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-700/50 flex items-center justify-center">
            <Activity className="w-8 h-8 text-gray-600 animate-pulse" />
          </div>
          <p className="text-gray-400 font-medium">Waiting for market data...</p>
          <p className="text-sm text-gray-500 mt-1">Signal checks will appear here when bars are processed</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-600/30 flex items-center justify-center">
            <Activity className="w-5 h-5 text-blue-400 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Live Signal Analysis</h3>
            <p className="text-xs text-gray-500">Monitoring {checksArray.length} symbol{checksArray.length > 1 ? 's' : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-400">LIVE</span>
        </div>
      </div>
      
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {checksArray.map(check => (
          <SignalCheckItem key={check.symbol} check={check} />
        ))}
      </div>
    </div>
  )
}
