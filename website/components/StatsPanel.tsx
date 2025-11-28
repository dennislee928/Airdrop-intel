'use client'

import { motion } from 'framer-motion'

interface AirdropEvent {
  status: 'active' | 'upcoming' | 'ended' | 'potential'
  source: string
}

interface WalletReport {
  has_defi_activity: boolean
}

interface Alert {
  priority: 'high' | 'medium' | 'low'
}

interface StatsPanelProps {
  events: AirdropEvent[]
  wallets: WalletReport[]
  alerts: Alert[]
}

export default function StatsPanel({ events, wallets, alerts }: StatsPanelProps) {
  const stats = {
    total: events.length,
    active: events.filter(e => e.status === 'active').length,
    upcoming: events.filter(e => e.status === 'upcoming').length,
    ended: events.filter(e => e.status === 'ended').length,
    potential: events.filter(e => e.status === 'potential').length,
    sources: {
      airdrops_io: events.filter(e => e.source === 'airdrops_io').length,
      cmc: events.filter(e => e.source === 'cmc_airdrops').length,
      icomarks: events.filter(e => e.source === 'icomarks_airdrops').length,
      altcoin: events.filter(e => e.source === 'altcointrading_airdrops').length,
    },
    wallets: wallets.length,
    walletsWithActivity: wallets.filter(w => w.has_defi_activity).length,
    alerts: alerts.length,
    highAlerts: alerts.filter(a => a.priority === 'high').length,
  }

  const statItems = [
    { label: 'TOTAL EVENTS', value: stats.total, color: 'var(--pixel-cyan)' },
    { label: 'ACTIVE', value: stats.active, color: 'var(--pixel-green)' },
    { label: 'UPCOMING', value: stats.upcoming, color: 'var(--pixel-yellow)' },
    { label: 'ALERTS', value: stats.alerts, color: 'var(--pixel-red)' },
  ]

  return (
    <div className="pixel-border bg-[var(--bg-secondary)] p-6 mb-8">
      <h2 className="text-2xl mb-6 pixel-text text-[var(--pixel-white)] text-center">
        📊 STATISTICS
      </h2>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {statItems.map((item, index) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.1, type: 'spring' }}
            className="pixel-card text-center"
          >
            <div className="text-xs mb-2 opacity-70">{item.label}</div>
            <div
              className="text-3xl font-bold pixel-text"
              style={{ color: item.color }}
            >
              {item.value}
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div className="pixel-card">
          <div className="opacity-70 mb-1">ENDED</div>
          <div className="text-xl status-ended">{stats.ended}</div>
        </div>
        <div className="pixel-card">
          <div className="opacity-70 mb-1">POTENTIAL</div>
          <div className="text-xl status-potential">{stats.potential}</div>
        </div>
        <div className="pixel-card">
          <div className="opacity-70 mb-1">WALLETS</div>
          <div className="text-xl text-[var(--pixel-cyan)]">{stats.wallets}</div>
        </div>
        <div className="pixel-card">
          <div className="opacity-70 mb-1">HIGH PRIORITY</div>
          <div className="text-xl text-[var(--pixel-red)]">{stats.highAlerts}</div>
        </div>
      </div>

      <div className="mt-6 pt-6 border-t-2 border-[var(--pixel-white)]">
        <h3 className="text-sm mb-4 text-center opacity-70">BY SOURCE</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="pixel-card text-center">
            <div className="opacity-70 mb-1">Airdrops.io</div>
            <div className="text-lg text-[var(--pixel-green)]">{stats.sources.airdrops_io}</div>
          </div>
          <div className="pixel-card text-center">
            <div className="opacity-70 mb-1">CoinMarketCap</div>
            <div className="text-lg text-[var(--pixel-cyan)]">{stats.sources.cmc}</div>
          </div>
          <div className="pixel-card text-center">
            <div className="opacity-70 mb-1">ICOMarks</div>
            <div className="text-lg text-[var(--pixel-yellow)]">{stats.sources.icomarks}</div>
          </div>
          <div className="pixel-card text-center">
            <div className="opacity-70 mb-1">AltcoinTrading</div>
            <div className="text-lg text-[var(--pixel-purple)]">{stats.sources.altcoin}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

