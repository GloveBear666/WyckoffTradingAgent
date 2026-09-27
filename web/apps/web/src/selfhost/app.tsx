import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api, type ChatMessage, type Config, type HistoryItem, type Report, type Selection } from './api'
import { Controls } from './controls'
import { AnalysisReport } from './report'

export function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('wyckoff-crypto-token') || '')
  const [input, setInput] = useState('')
  const [config, setConfig] = useState<Config | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!token) return
    let active = true
    api<Config>('config', token).then(value => { if (active) setConfig(value) }).catch(err => {
      if (active) { setError(String(err.message)); setConfig(null) }
    })
    return () => { active = false }
  }, [token])
  if (!config) return <main className="login"><div className="login-card"><span className="eyebrow">YOUR PRIVATE RESEARCH DESK</span><h1>Wyckoff Crypto<span>看清价格背后的结构。</span></h1>
    <p>连接你的研究服务器，分析现货与永续合约。</p>
    <form onSubmit={e => { e.preventDefault(); setError(''); sessionStorage.setItem('wyckoff-crypto-token', input); setToken(input) }}>
      <label>服务器访问口令<input type="password" autoComplete="current-password" value={input} onChange={e => setInput(e.target.value)} required /></label><button className="primary">进入研究工作台 →</button>
    </form>{error && <p className="error" role="alert">{error}</p>}<p className="quiet">口令获取方式见仓库的自托管部署说明。</p></div></main>
  return <Workspace token={token} config={config} logout={() => { sessionStorage.removeItem('wyckoff-crypto-token'); setToken(''); setConfig(null) }} />
}

function Workspace({ token, config, logout }: { token: string; config: Config; logout: () => void }) {
  const [selection, setSelection] = useState<Selection>({ exchange: 'okx', symbol: 'BTC/USDT', market: 'spot', timeframe: '1d', limit: 320 })
  const [report, setReport] = useState<Report | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const refresh = () => api<HistoryItem[]>('history', token).then(setHistory)
  useEffect(() => { api<HistoryItem[]>('history', token).then(setHistory).catch(err => setError(String(err.message))) }, [token])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, busy])
  async function run(chatMode: boolean) {
    setBusy(true); setError('')
    try {
      if (chatMode) {
        const next: ChatMessage[] = [...messages, { role: 'user', content: draft.trim() }]
        setDraft(''); setMessages(next)
        const result = await api<{ reply: string; reports: Report[] }>('chat', token, { context: selection, messages: next.slice(-20) })
        setMessages([...next, { role: 'assistant', content: result.reply }])
        setReport(result.reports.at(-1) || null)
      } else {
        const result = await api<Report>('analyze', token, selection)
        setReport(result)
        setMessages(previous => [...previous, { role: 'assistant', content: result.summary }])
      }
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : String(err)) }
    finally { setBusy(false) }
  }
  function restore(item: HistoryItem) {
    setReport(item.report)
    const meta = item.report.metadata
    setSelection({ exchange: meta.exchange, symbol: meta.symbol, market: meta.market as Selection['market'], timeframe: meta.timeframe, limit: 320 })
    setMessages([{ role: 'assistant', content: `历史研究（不是实时行情）：\n${item.report.summary}` }])
  }
  return <div className="workspace">
    <Controls selection={selection} setSelection={setSelection} config={config} busy={busy} analyze={() => void run(false)} history={history} restore={restore} logout={logout} />
    <main className="desk"><header className="topbar"><span>研究工作台 <span className="divider">/</span> Agent</span><span className="status"><i />{config.llm_enabled ? 'AI 对话已配置' : '结构分析模式'}</span></header>
      <div className="desk-content"><div className="desk-title"><span className="eyebrow">PRICE. VOLUME. STRUCTURE.</span><h1>加密市场读盘室</h1><p>从量价事实出发，观察下一步需要验证什么。</p></div>
      {report ? <AnalysisReport report={report} /> : <section className="empty"><div className="empty-chart">▁ ▂ ▄ ▃ ▅ ▄ ▇ ▆</div><h2>从一个交易对开始</h2><p>选择市场与周期，运行结构分析。<br />支持 BTC、ETH 及交易所提供的其他现货与线性永续交易对。</p><button onClick={() => void run(false)} disabled={busy}>分析 {selection.symbol} →</button></section>}
      <section className="conversation" aria-label="研究对话" aria-live="polite">{messages.map((message, index) => <article key={index} className={`message ${message.role}`}><span className="message-role">{message.role === 'user' ? 'YOU' : 'WYCKOFF'}</span><ReactMarkdown>{message.content}</ReactMarkdown></article>)}{busy && <p className="working">正在获取行情并分析，请稍候…</p>}<div ref={bottom} /></section>
      {error && <div className="error" role="alert">{error}</div>}
      <form className="composer" onSubmit={e => { e.preventDefault(); if (draft.trim() && !busy) void run(true) }}><textarea value={draft} onChange={e => setDraft(e.target.value)} disabled={!config.llm_enabled || busy} maxLength={12000} aria-label="研究问题" placeholder={config.llm_enabled ? '问一个具体问题，例如：比较 BTC 现货和永续的结构，哪些信号需要继续确认？' : '配置服务器 LLM_MODEL 后开启 AI 对话；现在可以使用左侧的免费结构分析。'} /><button className="primary" disabled={!config.llm_enabled || busy || !draft.trim()}>发送 ↑</button></form>
      <p className="footnote">仅供研究 · 信号尚未经过加密市场回测 · 所有图表时间为 UTC</p></div>
    </main>
  </div>
}
