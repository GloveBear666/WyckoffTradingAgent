import { number, type Report } from './api'
import { PriceChart } from './chart'

export function AnalysisReport({ report }: { report: Report }) {
  const { metadata: meta } = report
  const funding = meta.derivatives?.funding
  const oi = meta.derivatives?.open_interest
  return <section className="report">
    <header className="report-heading"><div><span className="eyebrow">{meta.exchange.toUpperCase()} / {meta.market === 'swap' ? '线性永续' : '现货'}</span>
      <h2>{meta.symbol} <span>{meta.timeframe}</span></h2></div>
      <div className="price">{number(report.latest_close)} <small>{meta.quote}</small><span className={report.change_pct >= 0 ? 'positive' : 'negative'}>{report.change_pct >= 0 ? '+' : ''}{report.change_pct.toFixed(2)}% <small>本根 K 线</small></span></div>
    </header>
    <PriceChart report={report} />
    <div className="metrics">{[['MA 20', report.ma20], ['MA 50', report.ma50], ['MA 200', report.ma200], ['ATR 14', report.atr14]].map(([label, value]) =>
      <div key={String(label)}><span>{label}</span><strong>{number(value as number | null)}</strong></div>)}</div>
    <div className="structure"><span className="badge">结构观察</span><strong>{report.stage}</strong><span>{report.signals.join(' · ') || '本根未触发结构信号'}</span></div>
    {meta.derivatives && <div className="derivatives">
      <p>资金费率 <strong>{funding?.fundingRate == null ? '不可用' : `${(funding.fundingRate * 100).toFixed(5)}%`}</strong> {funding?.interval ? `每 ${funding.interval}` : '结算周期未提供'}<small>资金费率时间：{funding?.fundingTimestamp ? new Date(funding.fundingTimestamp).toISOString() : '未提供'}</small></p>
      <p>未平仓量 <strong>{number(oi?.openInterestAmount)}</strong><small>交易所原生数量；名义价值 {number(oi?.openInterestValue)} · 时间 {oi?.timestamp ? new Date(oi.timestamp).toISOString() : '未提供'}</small></p>
    </div>}
    <footer className="data-note">{meta.bars} 根已收盘 K 线 · 最新开盘时间 {meta.last_candle_at} · UTC<br />
      获取时间 {meta.fetched_at} · 成交量为该交易所原生单位<br />{report.note}
      {meta.warnings.map(warning => <p key={warning}>{warning}</p>)}</footer>
  </section>
}
