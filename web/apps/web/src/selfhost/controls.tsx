import type { Config, HistoryItem, Selection } from './api'

interface Props {
  selection: Selection; setSelection: (value: Selection) => void; config: Config
  busy: boolean; analyze: () => void; history: HistoryItem[]; restore: (item: HistoryItem) => void; logout: () => void
}
export function Controls({ selection, setSelection, config, busy, analyze, history, restore, logout }: Props) {
  const update = (key: keyof Selection, value: string | number) => setSelection({ ...selection, [key]: value })
  return <aside className="sidebar">
    <a className="brand" href="/chat"><span className="brand-mark">W</span><div>WYCKOFF<small>CRYPTO RESEARCH</small></div></a>
    <div className="section-label">研究标的</div>
    <label>交易所<select aria-label="交易所" disabled={busy} value={selection.exchange} onChange={e => update('exchange', e.target.value)}>{config.exchanges.map(name => <option key={name} value={name}>{name.toUpperCase()}</option>)}</select></label>
    <label>市场<select aria-label="市场" disabled={busy} value={selection.market} onChange={e => setSelection({ ...selection, market: e.target.value as Selection['market'], symbol: selection.symbol.split(':')[0] || 'BTC/USDT' })}><option value="spot">现货</option><option value="swap">线性永续合约</option></select></label>
    <label>交易对<input disabled={busy} value={selection.symbol} onChange={e => update('symbol', e.target.value.toUpperCase())} placeholder="BTC/USDT" maxLength={50} /></label>
    <div className="pair-controls"><label>周期<select aria-label="周期" disabled={busy} value={selection.timeframe} onChange={e => update('timeframe', e.target.value)}>{config.timeframes.map(value => <option key={value}>{value}</option>)}</select></label>
    <label>K 线数量<select aria-label="K 线数量" disabled={busy} value={selection.limit} onChange={e => update('limit', Number(e.target.value))}>{[120, 320, 500].map(value => <option key={value}>{value}</option>)}</select></label></div>
    <button className="primary" disabled={busy} onClick={analyze}>{busy ? '正在研究…' : '运行结构分析 ↗'}</button>
    <p className="quiet">公开行情 · 无需交易所 Key<br />研究工具，不连接交易账户</p>
    <div className="section-label history-label">近期研究 <span>{history.length}</span></div>
    <div className="history">{history.length === 0 && <p className="quiet">分析完成后自动保存在服务器</p>}{history.map(item => <button disabled={busy} key={item.id} onClick={() => restore(item)}><strong>{item.report.metadata.symbol}</strong><small>{item.report.metadata.exchange} · {item.report.metadata.market} · {item.report.metadata.timeframe}</small><small>{item.created_at} UTC</small></button>)}</div>
    <button className="logout" onClick={logout}>退出工作台</button>
  </aside>
}
