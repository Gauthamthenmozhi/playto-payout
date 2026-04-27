import { useEffect, useState } from "react";

const API = process.env.REACT_APP_API_URL || "";

const STATUS_STYLES = {
  completed: "bg-green-100 text-green-700 ring-1 ring-green-200",
  failed:    "bg-red-100 text-red-700 ring-1 ring-red-200",
  processing:"bg-amber-100 text-amber-700 ring-1 ring-amber-200",
  pending:   "bg-gray-100 text-gray-600 ring-1 ring-gray-200",
};

export default function App() {
  const [merchants, setMerchants]   = useState([]);
  const [merchant, setMerchant]     = useState(null);
  const [merchantId, setMerchantId] = useState(null);
  const [amount, setAmount]         = useState("");
  const [message, setMessage]       = useState({ text: "", ok: true });
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    fetch(`${API}/api/v1/merchants/`)
      .then(r => r.json())
      .then(data => {
        setMerchants(data);
        if (data.length > 0) setMerchantId(data[0].id);
      });
  }, []);

  const fetchMerchant = async (id) => {
    const res  = await fetch(`${API}/api/v1/merchants/${id}/`);
    const data = await res.json();
    setMerchant(data);
  };

  useEffect(() => {
    if (!merchantId) return;
    fetchMerchant(merchantId);
    const interval = setInterval(() => fetchMerchant(merchantId), 5000);
    return () => clearInterval(interval);
  }, [merchantId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function requestPayout() {
    if (!amount) return;
    setLoading(true);
    setMessage({ text: "", ok: true });
    const res  = await fetch(`${API}/api/v1/payouts/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        merchant_id:    merchantId,
        amount_paise:   Number(amount) * 100,
        bank_account_id:"ACC123456",
      }),
    });
    const data = await res.json();
    setLoading(false);
    if (res.ok) {
      setMessage({ text: "✓ Payout requested successfully!", ok: true });
      setAmount("");
      fetchMerchant(merchantId);
    } else {
      setMessage({ text: data.error || "Something went wrong", ok: false });
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top navbar */}
      <nav className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">P</span>
          </div>
          <span className="text-slate-800 font-semibold text-lg">Playto Pay</span>
          <span className="text-slate-400 text-sm">/ Payout Dashboard</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block"></span>
          <span className="text-slate-500 text-sm">Live</span>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-8">

        {/* Merchant switcher */}
        <div className="mb-6">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Select Merchant</p>
          <div className="flex gap-2 flex-wrap">
            {merchants.map(m => (
              <button
                key={m.id}
                onClick={() => { setMerchantId(m.id); setMessage({ text: "", ok: true }); }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  merchantId === m.id
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "bg-white text-slate-600 border border-slate-200 hover:border-indigo-300 hover:text-indigo-600"
                }`}
              >
                {m.name}
              </button>
            ))}
          </div>
        </div>

        {merchant && (
          <>
            {/* Balance cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Available Balance</p>
                <p className="text-3xl font-bold text-green-600">
                  ₹{(merchant.balance_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </p>
                <p className="text-xs text-slate-400 mt-1">Ready to withdraw</p>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Held Balance</p>
                <p className="text-3xl font-bold text-amber-500">
                  ₹{(merchant.held_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </p>
                <p className="text-xs text-slate-400 mt-1">Pending / processing</p>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Merchant</p>
                <p className="text-base font-semibold text-slate-800 mt-1">{merchant.name}</p>
                <p className="text-xs text-slate-400 mt-1">{merchant.email}</p>
              </div>
            </div>

            {/* Payout form */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm mb-6">
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-4">Request Payout</h2>
              <div className="flex gap-3">
                <div className="relative flex-1">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium">₹</span>
                  <input
                    type="number"
                    placeholder="0.00"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    className="w-full pl-8 pr-4 py-2.5 border border-slate-200 rounded-lg text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={requestPayout}
                  disabled={loading || !amount}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white text-sm font-medium rounded-lg transition-colors duration-150"
                >
                  {loading ? "Processing..." : "Withdraw"}
                </button>
              </div>
              {message.text && (
                <p className={`mt-3 text-sm font-medium ${message.ok ? "text-green-600" : "text-red-600"}`}>
                  {message.text}
                </p>
              )}
            </div>

            {/* Payout history */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm mb-6">
              <div className="px-6 py-4 border-b border-slate-100">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Payout History</h2>
              </div>
              {merchant.payouts.length === 0 ? (
                <p className="text-slate-400 text-sm text-center py-10">No payouts yet</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Amount</th>
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Bank Account</th>
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {merchant.payouts.map(p => (
                      <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-3 font-semibold text-slate-800">
                          ₹{(p.amount_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-3">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[p.status]}`}>
                            {p.status}
                          </span>
                        </td>
                        <td className="px-6 py-3 text-slate-500 font-mono text-xs">{p.bank_account_id || "ACC123456"}</td>
                        <td className="px-6 py-3 text-slate-400 text-xs">
                          {new Date(p.created_at).toLocaleString("en-IN")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Recent transactions */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
              <div className="px-6 py-4 border-b border-slate-100">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Recent Transactions</h2>
              </div>
              {merchant.transactions.length === 0 ? (
                <p className="text-slate-400 text-sm text-center py-10">No transactions yet</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Type</th>
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Amount</th>
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Description</th>
                      <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {merchant.transactions.map((t, i) => (
                      <tr key={i} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-3">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            t.type === "credit"
                              ? "bg-green-100 text-green-700 ring-1 ring-green-200"
                              : "bg-red-100 text-red-700 ring-1 ring-red-200"
                          }`}>
                            {t.type === "credit" ? "↑ CREDIT" : "↓ DEBIT"}
                          </span>
                        </td>
                        <td className={`px-6 py-3 font-semibold ${t.type === "credit" ? "text-green-600" : "text-red-600"}`}>
                          {t.type === "credit" ? "+" : "-"}₹{(t.amount_paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-3 text-slate-500">{t.description}</td>
                        <td className="px-6 py-3 text-slate-400 text-xs">
                          {new Date(t.created_at).toLocaleString("en-IN")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
