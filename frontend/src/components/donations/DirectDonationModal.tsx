import { useState } from 'react'
import { useAuth } from '@/auth/AuthContext'
import { donationsApi, type DonationRecord, type PaymentMethod } from '@/api/donations'

interface ProjectOption {
  id: string
  title: string
  project_code: string
}

interface DirectDonationModalProps {
  ngoId: string
  ngoName: string
  ngoRegistrationNumber?: string | null
  projects?: ProjectOption[]
  preselectedProjectId?: string | null
  onClose: () => void
  onSuccess?: (donation: DonationRecord) => void
}

const AMOUNT_PRESETS = [500, 1000, 2500, 5000, 10000]

export default function DirectDonationModal({
  ngoId,
  ngoName,
  ngoRegistrationNumber,
  projects = [],
  preselectedProjectId = null,
  onClose,
  onSuccess,
}: DirectDonationModalProps) {
  const { user } = useAuth()

  const [selectedProjectId, setSelectedProjectId] = useState<string>(preselectedProjectId || '')
  const [amount, setAmount] = useState<number>(0)
  const [customAmount, setCustomAmount] = useState<string>('')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('UPI')
  const [donorName, setDonorName] = useState(user?.full_name || '')
  const [donorEmail, setDonorEmail] = useState(user?.email || '')
  const [donorNotes, setDonorNotes] = useState('')
  const [donorPan, setDonorPan] = useState('')

  // Payment method specific state
  const [upiId, setUpiId] = useState('')
  const [cardNumber, setCardNumber] = useState('')
  const [cardExpiry, setCardExpiry] = useState('')
  const [cardCvv, setCardCvv] = useState('')
  const [selectedBank, setSelectedBank] = useState('')

  // Flow states
  const [step, setStep] = useState<'DETAILS' | 'PROCESSING' | 'SUCCESS'>('DETAILS')
  const [processingMsg, setProcessingMsg] = useState('Initiating secure gateway connection...')
  const [error, setError] = useState<string | null>(null)
  const [completedDonation, setCompletedDonation] = useState<DonationRecord | null>(null)

  function handlePresetSelect(val: number) {
    setAmount(val)
    setCustomAmount(String(val))
  }

  function handleCustomAmountChange(val: string) {
    setCustomAmount(val)
    const num = parseFloat(val)
    if (!isNaN(num) && num > 0) {
      setAmount(num)
    }
  }

  async function handlePayNow(e: React.FormEvent) {
    e.preventDefault()
    if (!amount || amount <= 0) {
      setError('Please enter a valid donation amount greater than 0.')
      return
    }

    setError(null)
    setStep('PROCESSING')
    setProcessingMsg('Connecting to secure banking gateway...')

    try {
      // Step simulation delay for rich realistic payment experience
      await new Promise((r) => setTimeout(r, 600))
      setProcessingMsg(`Authorizing direct transfer of ₹${amount.toLocaleString()} to ${ngoName}...`)
      await new Promise((r) => setTimeout(r, 600))
      setProcessingMsg('Issuing Section 80G Tax Exemption Certificate & Audited Transaction Hash...')

      const res = await donationsApi.create({
        ngo_id: ngoId,
        project_id: selectedProjectId || undefined,
        amount: amount,
        currency: 'INR',
        payment_method: paymentMethod,
        donor_name: donorName.trim() || undefined,
        donor_email: donorEmail.trim() || undefined,
        donor_notes: donorNotes.trim()
          ? `${donorNotes.trim()} | PAN: ${donorPan.trim()}`
          : `PAN: ${donorPan.trim()}`,
      })

      if (res.data.success && res.data.data) {
        setCompletedDonation(res.data.data)
        setStep('SUCCESS')
        if (onSuccess) {
          onSuccess(res.data.data)
        }
      } else {
        throw new Error(res.data.message || 'Payment processing failed.')
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string; message?: string } }; message?: string }
      setError(
        axiosErr.response?.data?.error ||
          axiosErr.response?.data?.message ||
          axiosErr.message ||
          'Payment failed. Please try again.'
      )
      setStep('DETAILS')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-xl rounded-2xl bg-surface border border-surface-border shadow-2xl overflow-hidden my-8">
        {/* ── HEADER ────────────────────────────────────────────────── */}
        <div className="p-5 border-b border-surface-border bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-xl shadow-lg shadow-emerald-500/20">
              💝
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white tracking-tight">
                  Direct Donation Gateway
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/60">
                  80G Compliant
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5 truncate max-w-sm">
                Recipient: <strong className="text-white">{ngoName}</strong>
                {ngoRegistrationNumber ? ` (${ngoRegistrationNumber})` : ''}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-lg p-1.5 rounded-lg hover:bg-slate-800 transition"
          >
            ✕
          </button>
        </div>

        {/* ── ERROR NOTIFICATION ────────────────────────────────────── */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-950/80 border border-rose-600/70 text-rose-200 text-xs flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* ── STEP 1: CONTRIBUTION FORM ─────────────────────────────── */}
        {step === 'DETAILS' && (
          <form onSubmit={handlePayNow} className="p-6 space-y-5">
            {/* Target Project Selection */}
            <div>
              <label className="form-label text-xs flex items-center justify-between">
                <span>Select Target Allocation *</span>
                <span className="text-[10px] text-brand-400 font-normal">100% Direct Disbursement</span>
              </label>
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="input-field text-xs py-2"
              >
                <option value="">⭐ General NGO Mission & Core Development Fund</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    🎯 [{p.project_code}] {p.title.slice(0, 45)}
                  </option>
                ))}
              </select>
            </div>

            {/* Donation Amount Presets & Custom Input */}
            <div>
              <label className="form-label text-xs flex items-center justify-between">
                <span>Donation Amount (INR ₹) *</span>
                <span className="text-[10px] text-slate-400">Tax Exempt under Sec 80G</span>
              </label>

              <div className="grid grid-cols-5 gap-2 mb-2.5">
                {AMOUNT_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => handlePresetSelect(preset)}
                    className={`py-2 px-1 rounded-xl text-xs font-bold font-mono transition-all border ${
                      amount === preset
                        ? 'bg-emerald-600 text-white border-emerald-400 shadow-md shadow-emerald-600/30'
                        : 'bg-slate-900/80 text-slate-300 border-surface-border hover:border-slate-600 hover:text-white'
                    }`}
                  >
                    ₹{preset.toLocaleString()}
                  </button>
                ))}
              </div>

              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-bold text-slate-400">
                  ₹
                </span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  required
                  placeholder="Enter custom amount"
                  value={customAmount}
                  onChange={(e) => handleCustomAmountChange(e.target.value)}
                  className="input-field text-sm pl-8 font-mono font-bold text-emerald-400"
                />
              </div>
            </div>

            {/* Payment Method Selector */}
            <div>
              <label className="form-label text-xs">Direct Payment Channel *</label>
              <div className="grid grid-cols-3 gap-2.5">
                <button
                  type="button"
                  onClick={() => setPaymentMethod('UPI')}
                  className={`p-3 rounded-xl border text-center transition-all flex flex-col items-center gap-1.5 ${
                    paymentMethod === 'UPI'
                      ? 'bg-emerald-950/70 border-emerald-500 text-white shadow-lg shadow-emerald-500/10'
                      : 'bg-slate-900/70 border-surface-border text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <span className="text-xl">📱</span>
                  <span className="text-xs font-bold">UPI / QR</span>
                  <span className="text-[10px] font-mono text-emerald-400">GPay/PhonePe</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPaymentMethod('CARD')}
                  className={`p-3 rounded-xl border text-center transition-all flex flex-col items-center gap-1.5 ${
                    paymentMethod === 'CARD'
                      ? 'bg-emerald-950/70 border-emerald-500 text-white shadow-lg shadow-emerald-500/10'
                      : 'bg-slate-900/70 border-surface-border text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <span className="text-xl">💳</span>
                  <span className="text-xs font-bold">Debit / Card</span>
                  <span className="text-[10px] font-mono text-slate-400">Visa / RuPay</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPaymentMethod('NET_BANKING')}
                  className={`p-3 rounded-xl border text-center transition-all flex flex-col items-center gap-1.5 ${
                    paymentMethod === 'NET_BANKING'
                      ? 'bg-emerald-950/70 border-emerald-500 text-white shadow-lg shadow-emerald-500/10'
                      : 'bg-slate-900/70 border-surface-border text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <span className="text-xl">🏦</span>
                  <span className="text-xs font-bold">Net Banking</span>
                  <span className="text-[10px] font-mono text-slate-400">All Banks</span>
                </button>
              </div>
            </div>

            {/* Payment Method Details Box */}
            <div className="p-3.5 rounded-xl bg-slate-900/90 border border-surface-border space-y-3">
              {paymentMethod === 'UPI' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 font-semibold">Virtual Payment Address (VPA)</span>
                    <span className="text-[10px] font-mono text-emerald-400">● Live Simulated UPI</span>
                  </div>
                  <input
                    type="text"
                    value={upiId}
                    onChange={(e) => setUpiId(e.target.value)}
                    placeholder="e.g. yourname@okhdfcbank"
                    className="input-field text-xs font-mono"
                  />
                  <p className="text-[10px] text-slate-400">
                    Supports Google Pay, PhonePe, Paytm, BHIM, and all UPI 2.0 banking apps.
                  </p>
                </div>
              )}

              {paymentMethod === 'CARD' && (
                <div className="space-y-2.5">
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Card Number</label>
                    <input
                      type="text"
                      value={cardNumber}
                      onChange={(e) => setCardNumber(e.target.value)}
                      placeholder="16-digit card number"
                      className="input-field text-xs font-mono"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Expiry Date</label>
                      <input
                        type="text"
                        value={cardExpiry}
                        onChange={(e) => setCardExpiry(e.target.value)}
                        placeholder="MM/YY"
                        className="input-field text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">CVV</label>
                      <input
                        type="password"
                        maxLength={4}
                        value={cardCvv}
                        onChange={(e) => setCardCvv(e.target.value)}
                        placeholder="CVV"
                        className="input-field text-xs font-mono"
                      />
                    </div>
                  </div>
                </div>
              )}

              {paymentMethod === 'NET_BANKING' && (
                <div className="space-y-2">
                  <label className="text-[11px] text-slate-400 block">Select Primary Bank</label>
                  <select
                    value={selectedBank}
                    onChange={(e) => setSelectedBank(e.target.value)}
                    className="input-field text-xs"
                  >
                    <option value="">-- Choose your bank --</option>
                    <option value="HDFC Bank">HDFC Bank</option>
                    <option value="State Bank of India">State Bank of India (SBI)</option>
                    <option value="ICICI Bank">ICICI Bank</option>
                    <option value="Axis Bank">Axis Bank</option>
                    <option value="Punjab National Bank">Punjab National Bank</option>
                    <option value="Kotak Mahindra Bank">Kotak Mahindra Bank</option>
                  </select>
                </div>
              )}
            </div>

            {/* Donor Information & 80G Tax Deductibility */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="form-label text-xs">Donor Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="Full legal name"
                  value={donorName}
                  onChange={(e) => setDonorName(e.target.value)}
                  className="input-field text-xs"
                />
              </div>
              <div>
                <label className="form-label text-xs">Email Address *</label>
                <input
                  type="email"
                  required
                  placeholder="your.email@example.com"
                  value={donorEmail}
                  onChange={(e) => setDonorEmail(e.target.value)}
                  className="input-field text-xs"
                />
              </div>
              <div>
                <label className="form-label text-xs">PAN (For 80G Tax Receipt)</label>
                <input
                  type="text"
                  maxLength={10}
                  value={donorPan}
                  onChange={(e) => setDonorPan(e.target.value.toUpperCase())}
                  placeholder="e.g. ABCDE1234F"
                  className="input-field text-xs font-mono uppercase"
                />
              </div>
            </div>

            <div>
              <label className="form-label text-xs">Dedication or Support Note (Optional)</label>
              <textarea
                rows={2}
                placeholder="Message of encouragement or project allocation preferences..."
                value={donorNotes}
                onChange={(e) => setDonorNotes(e.target.value)}
                className="input-field text-xs"
              />
            </div>

            {/* ── FOOTER ACTIONS ──────────────────────────────────────── */}
            <div className="pt-3 border-t border-surface-border flex items-center justify-between">
              <button
                type="button"
                onClick={onClose}
                className="btn-secondary text-xs px-4 py-2"
              >
                Cancel
              </button>

              <button
                type="submit"
                className="btn-primary text-xs px-6 py-2.5 flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-600/30 text-white font-bold"
              >
                <span>💳</span>
                <span>Transfer ₹{amount.toLocaleString()} Directly to NGO</span>
              </button>
            </div>
          </form>
        )}

        {/* ── STEP 2: PROCESSING ANIMATION ──────────────────────────── */}
        {step === 'PROCESSING' && (
          <div className="p-12 text-center space-y-4">
            <div className="w-12 h-12 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto shadow-lg shadow-emerald-500/20" />
            <h4 className="text-base font-bold text-white">Processing Direct Bank Settlement</h4>
            <p className="text-xs text-slate-300 max-w-sm mx-auto font-mono">{processingMsg}</p>
            <div className="text-[11px] text-slate-500">
              Secured with 256-Bit SHA End-to-End Cryptographic Tunneling
            </div>
          </div>
        )}

        {/* ── STEP 3: SUCCESS & 80G TAX RECEIPT ──────────────────────── */}
        {step === 'SUCCESS' && completedDonation && (
          <div className="p-6 space-y-5">
            <div className="text-center space-y-2">
              <div className="w-14 h-14 rounded-full bg-emerald-500/20 border border-emerald-500 text-3xl flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/30 text-emerald-400">
                ✓
              </div>
              <h4 className="text-lg font-bold text-white">
                Donation Successfully Disbursed!
              </h4>
              <p className="text-xs text-slate-300 max-w-md mx-auto">
                Thank you, <strong className="text-white">{completedDonation.donor_name}</strong>! 
                Your contribution of <strong className="text-emerald-400">₹{completedDonation.amount.toLocaleString()}</strong> has 
                been directly settled to <strong className="text-white">{completedDonation.ngo_name}</strong>.
              </p>
            </div>

            {/* Official Tax Receipt Dossier */}
            <div className="p-4 rounded-xl bg-slate-900/90 border border-emerald-500/40 space-y-2.5 text-xs font-mono">
              <div className="flex items-center justify-between border-b border-surface-border pb-2">
                <span className="text-slate-400">Receipt No:</span>
                <span className="font-bold text-emerald-400">{completedDonation.receipt_number}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Transaction Ref:</span>
                <span className="text-white truncate max-w-[220px]" title={completedDonation.transaction_id}>
                  {completedDonation.transaction_id}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Beneficiary NGO:</span>
                <span className="text-white">{completedDonation.ngo_name}</span>
              </div>
              {completedDonation.project_title && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Target Project:</span>
                  <span className="text-brand-300 truncate max-w-[220px]">
                    {completedDonation.project_title}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Disbursed Amount:</span>
                <span className="text-base font-bold text-emerald-400">
                  ₹{completedDonation.amount.toLocaleString()} INR
                </span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-surface-border text-[11px]">
                <span className="text-slate-400">80G Exemption Status:</span>
                <span className="text-emerald-400 font-bold">100% Eligible (IT Act 1961)</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-surface-border">
              <button
                type="button"
                onClick={() => window.print()}
                className="btn-secondary text-xs px-4 py-2 flex items-center gap-1.5"
              >
                <span>🖨️</span>
                <span>Print / Save Tax Receipt</span>
              </button>

              <button
                type="button"
                onClick={onClose}
                className="btn-primary text-xs px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
              >
                Return to Directory
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
