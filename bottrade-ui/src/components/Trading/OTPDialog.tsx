import React, { useState, useRef, useEffect, useCallback } from 'react'
import { X, Loader2, CheckCircle, AlertCircle, ShieldCheck } from 'lucide-react'
import { useApi } from '../../hooks/useApi'
import useAppStore from '../../store/appStore'
import type { Signal } from '../../types/api'

interface OTPDialogProps {
  isOpen: boolean
  onClose: () => void
  signal: Signal | null
  onOrderPlaced?: (success: boolean, message: string) => void
}

type DialogStep = 'requesting' | 'input' | 'authenticating' | 'placing' | 'success' | 'error'

export default function OTPDialog({ isOpen, onClose, signal, onOrderPlaced }: OTPDialogProps) {
  const { post } = useApi()
  const { demoMode, settings } = useAppStore()
  
  const [step, setStep] = useState<DialogStep>('requesting')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string>('')
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])
  const hasRequestedOtp = useRef(false)  // Prevent double request
  
  // Check if this is auth-only mode (no real signal, just authenticate)
  const isAuthOnly = signal?.symbol === 'AUTH' || signal?.id === 0

  // Request OTP from server
  const requestOTP = useCallback(async () => {
    // Prevent double request
    if (hasRequestedOtp.current) {
      console.log('[OTP] Already requested, skipping duplicate')
      return
    }
    hasRequestedOtp.current = true
    
    try {
      setStep('requesting')
      setError(null)
      console.log('[OTP] Requesting OTP...')
      await post('/api/v1/trading/request-otp', {})
      console.log('[OTP] OTP request successful')
      setStep('input')
      // Focus first input after a small delay
      setTimeout(() => inputRefs.current[0]?.focus(), 100)
    } catch (err: any) {
      console.error('[OTP] Request failed:', err)
      setError(err?.response?.data?.detail || err?.message || 'Không thể gửi OTP. Vui lòng thử lại.')
      setStep('error')
    }
  }, [post])

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen && signal) {
      console.log('[OTP] Dialog opened, resetting state')
      setOtp(['', '', '', '', '', ''])
      setError(null)
      hasRequestedOtp.current = false  // Reset the flag
      requestOTP()
    }
    
    // Cleanup when dialog closes
    return () => {
      if (!isOpen) {
        hasRequestedOtp.current = false
      }
    }
  }, [isOpen])  // Only depend on isOpen, not signal

  // Handle OTP input change
  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return // Only allow digits
    
    const newOtp = [...otp]
    newOtp[index] = value.slice(-1) // Only take last digit
    setOtp(newOtp)

    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }

    // Auto-submit when all 6 digits entered
    if (newOtp.every(d => d !== '') && newOtp.join('').length === 6) {
      handleAuthenticate(newOtp.join(''))
    }
  }

  // Handle backspace
  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  // Authenticate with OTP
  const handleAuthenticate = async (otpCode: string) => {
    try {
      setStep('authenticating')
      setError(null)
      
      console.log('[OTP] Authenticating with OTP:', otpCode)
      const response = await post('/api/v1/trading/authenticate', { otp: otpCode })
      console.log('[OTP] Authentication response:', response)
      
      // Auth-only mode: Just authenticate, don't place order
      if (isAuthOnly) {
        setStep('success')
        setMessage('✅ Xác thực thành công! Trading token có hiệu lực trong 8 tiếng. Bot có thể tự động đặt lệnh khi có signal.')
        onOrderPlaced?.(true, 'Authentication successful')
        return
      }
      
      // Demo mode: Authenticate but don't place real order
      if (demoMode) {
        setStep('success')
        setMessage('🎭 Demo Mode: Xác thực thành công! Lệnh sẽ không được đặt thật.')
        onOrderPlaced?.(true, 'Demo: Authentication successful')
        return
      }

      // Live mode with real signal: Place the order
      await placeOrder()
    } catch (err: any) {
      console.error('[OTP] Authentication error:', err)
      // Extract error message from various error formats
      const errorMessage = 
        err?.response?.data?.detail || 
        err?.message || 
        'OTP không hợp lệ hoặc đã hết hạn.'
      setError(errorMessage)
      setStep('input')
      setOtp(['', '', '', '', '', ''])
      setTimeout(() => inputRefs.current[0]?.focus(), 100)
    }
  }

  // Place the actual order
  const placeOrder = async () => {
    if (!signal) return
    
    try {
      setStep('placing')
      const quantity = settings?.default_quantity || 100
      
      await post('/api/v1/trading/orders', {
        symbol: signal.symbol,
        quantity: quantity,
        price: signal.entry
      })
      
      setStep('success')
      setMessage(`✅ Đã đặt lệnh MUA ${signal.symbol} thành công! SL: ${signal.quantity} cổ phiếu @ ${signal.entry.toLocaleString()}đ`)
      onOrderPlaced?.(true, 'Order placed successfully')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Không thể đặt lệnh. Vui lòng thử lại.')
      setStep('error')
      onOrderPlaced?.(false, err?.response?.data?.detail || 'Order failed')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={step === 'success' || step === 'error' ? onClose : undefined}
      />
      
      {/* Dialog */}
      <div className="relative bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">
              {isAuthOnly ? 'Xác thực Trading' : 'Xác thực đặt lệnh'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Auth-only mode info */}
          {isAuthOnly && (
            <div className="mb-6 p-4 bg-blue-900/30 rounded-lg border border-blue-600/50">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck className="w-5 h-5 text-blue-400" />
                <span className="text-blue-300 font-medium">Xác thực cho Auto-Trade</span>
              </div>
              <p className="text-sm text-gray-300">
                Nhập mã OTP để xác thực. Sau khi xác thực, bot có thể tự động đặt lệnh trong <strong className="text-blue-300">8 tiếng</strong> tiếp theo.
              </p>
            </div>
          )}
          
          {/* Signal Info - only show for real signals */}
          {signal && !isAuthOnly && (
            <div className="mb-6 p-4 bg-gray-900 rounded-lg border border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400">Mã CK:</span>
                <span className="text-white font-bold text-lg">{signal.symbol}</span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400">Loại lệnh:</span>
                <span className={`font-medium ${signal.signal_type === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                  {signal.signal_type === 'BUY' ? '🟢 MUA' : '🔴 BÁN'}
                </span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400">Giá vào:</span>
                <span className="text-white">{signal.entry.toLocaleString('vi-VN')}đ</span>
              </div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400">Stop Loss:</span>
                <span className="text-red-400">{signal.stop_loss.toLocaleString('vi-VN')}đ</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Take Profit:</span>
                <span className="text-green-400">{signal.take_profit.toLocaleString('vi-VN')}đ</span>
              </div>
              {demoMode && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <span className="text-purple-400 text-sm">🎭 Demo Mode - Không đặt lệnh thật</span>
                </div>
              )}
            </div>
          )}

          {/* Step: Requesting OTP */}
          {step === 'requesting' && (
            <div className="text-center py-8">
              <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
              <p className="text-gray-300">Đang gửi mã OTP qua email...</p>
              <p className="text-gray-500 text-sm mt-2">Vui lòng chờ trong giây lát</p>
            </div>
          )}

          {/* Step: Input OTP */}
          {step === 'input' && (
            <div className="space-y-4">
              <p className="text-center text-gray-300 mb-4">
                Nhập mã OTP 6 số đã được gửi đến email của bạn
              </p>
              
              {/* OTP Inputs */}
              <div className="flex justify-center gap-2">
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={el => { inputRefs.current[index] = el }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={e => handleOtpChange(index, e.target.value)}
                    onKeyDown={e => handleKeyDown(index, e)}
                    className="w-12 h-14 text-center text-2xl font-bold bg-gray-900 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 outline-none transition"
                  />
                ))}
              </div>

              {error && (
                <div className="flex items-center gap-2 text-red-400 text-sm justify-center mt-4">
                  <AlertCircle className="w-4 h-4" />
                  {error}
                </div>
              )}

              <div className="flex justify-center mt-4">
                <button
                  onClick={requestOTP}
                  className="text-blue-400 hover:text-blue-300 text-sm underline"
                >
                  Gửi lại mã OTP
                </button>
              </div>
            </div>
          )}

          {/* Step: Authenticating */}
          {step === 'authenticating' && (
            <div className="text-center py-8">
              <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
              <p className="text-gray-300">Đang xác thực OTP...</p>
            </div>
          )}

          {/* Step: Placing Order */}
          {step === 'placing' && (
            <div className="text-center py-8">
              <Loader2 className="w-12 h-12 text-green-400 animate-spin mx-auto mb-4" />
              <p className="text-gray-300">Đang đặt lệnh...</p>
              <p className="text-gray-500 text-sm mt-2">Vui lòng không đóng cửa sổ này</p>
            </div>
          )}

          {/* Step: Success */}
          {step === 'success' && (
            <div className="text-center py-8">
              <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />
              <p className="text-green-400 font-medium text-lg mb-2">Thành công!</p>
              <p className="text-gray-300">{message}</p>
              <button
                onClick={onClose}
                className="mt-6 px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition"
              >
                Đóng
              </button>
            </div>
          )}

          {/* Step: Error */}
          {step === 'error' && (
            <div className="text-center py-8">
              <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
              <p className="text-red-400 font-medium text-lg mb-2">Lỗi!</p>
              <p className="text-gray-300">{error}</p>
              <div className="flex gap-3 justify-center mt-6">
                <button
                  onClick={() => {
                    setError(null)
                    requestOTP()
                  }}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
                >
                  Thử lại
                </button>
                <button
                  onClick={onClose}
                  className="px-6 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition"
                >
                  Đóng
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
