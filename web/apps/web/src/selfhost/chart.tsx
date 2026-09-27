import { useEffect, useRef } from 'react'
import { CandlestickSeries, createChart, HistogramSeries, type UTCTimestamp } from 'lightweight-charts'
import type { Report } from './api'

export function PriceChart({ report }: { report: Report }) {
  const element = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!element.current) return
    const chart = createChart(element.current, {
      autoSize: true, height: 360,
      layout: { background: { color: '#141e1c' }, textColor: '#9caeaa', attributionLogo: true },
      grid: { vertLines: { color: '#20302b' }, horzLines: { color: '#20302b' } },
      timeScale: { timeVisible: true, secondsVisible: false },
      rightPriceScale: { scaleMargins: { top: 0.08, bottom: 0.25 } },
    })
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#78d5ad', downColor: '#ed938e', borderVisible: false,
      wickUpColor: '#78d5ad', wickDownColor: '#ed938e',
      priceFormat: { type: 'custom', minMove: 0.00000001, formatter: (value: number) => value.toPrecision(7) },
    })
    candles.setData(report.candles.map(c => ({ ...c, time: c.time as UTCTimestamp })))
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' })
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.83, bottom: 0 } })
    volume.setData(report.candles.map(c => ({ time: c.time as UTCTimestamp, value: c.volume, color: c.close >= c.open ? '#345a4d' : '#633f3d' })))
    if (report.trading_range) {
      for (const [title, price] of [['支撑', report.trading_range.support], ['阻力', report.trading_range.resistance]] as const) {
        candles.createPriceLine({ price, title, color: '#c5b584', lineWidth: 1, axisLabelVisible: true })
      }
    }
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [report])
  return <div ref={element} className="price-chart" aria-label={`${report.metadata.symbol} K 线及成交量，UTC`} />
}
