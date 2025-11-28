'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import AirdropList from '@/components/AirdropList'
import StatsPanel from '@/components/StatsPanel'
import Header from '@/components/Header'
import LoadingScreen from '@/components/LoadingScreen'
import './globals.css'

interface AirdropEvent {
  token: string | null
  project: string
  campaign_name: string
  source: string
  status: 'active' | 'upcoming' | 'ended' | 'potential'
  type: string
  reward_type: string
  est_value_usd: number | null
  deadline: string | null
  requirements: string[]
  links: {
    details: string
  }
}

interface WalletReport {
  name: string
  chain: string
  address: string
  tx_count: number
  has_defi_activity: boolean
}

interface Alert {
  id: string
  type: string
  priority: 'high' | 'medium' | 'low'
  project: string
  message: string
  links: Record<string, string>
}

export default function Home() {
  const [events, setEvents] = useState<AirdropEvent[]>([])
  const [wallets, setWallets] = useState<WalletReport[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<string>('')

  useEffect(() => {
    loadData()
    // 每 5 分鐘自動刷新
    const interval = setInterval(loadData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [eventsRes, walletsRes, alertsRes] = await Promise.all([
        fetch('/data/events_sources.json').catch(() => ({ ok: false } as Response)),
        fetch('/data/wallets_report.json').catch(() => ({ ok: false } as Response)),
        fetch('/data/alerts.json').catch(() => ({ ok: false } as Response)),
      ])

      if (eventsRes.ok) {
        try {
          const eventsData = await eventsRes.json()
          setEvents(Array.isArray(eventsData) ? eventsData : [])
        } catch (e) {
          console.error('解析 events_sources.json 失敗:', e)
          setEvents([])
        }
      } else {
        setEvents([])
      }

      if (walletsRes?.ok) {
        try {
          const walletsData = await walletsRes.json()
          setWallets(Array.isArray(walletsData) ? walletsData : [])
        } catch (e) {
          console.error('解析 wallets_report.json 失敗:', e)
          setWallets([])
        }
      } else {
        setWallets([])
      }

      if (alertsRes?.ok) {
        try {
          const alertsData = await alertsRes.json()
          setAlerts(Array.isArray(alertsData) ? alertsData : [])
        } catch (e) {
          console.error('解析 alerts.json 失敗:', e)
          setAlerts([])
        }
      } else {
        setAlerts([])
      }

      setLastUpdate(new Date().toLocaleString('zh-TW'))
    } catch (error) {
      console.error('載入數據失敗:', error)
      setEvents([])
      setWallets([])
      setAlerts([])
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <LoadingScreen />
  }

  return (
    <div className="scanlines grid-bg min-h-screen">
      <Header lastUpdate={lastUpdate} />
      <div className="flex justify-center">
        <a href="https://discord.gg/2Fk6zJ6t">
          <button className="pixel-button">Join our Discord</button>
        </a>
      </div>
      <main className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <StatsPanel events={events} wallets={wallets} alerts={alerts} />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <AirdropList events={events} alerts={alerts} />
        </motion.div>
      </main>

      <footer className="text-center py-8 text-xs opacity-70">
        <p className="pixel-text">
          Airdrop Intel Pipeline v1.0 | Last Update: {lastUpdate || 'Loading...'}
        </p>
      </footer>
    </div>
  )
}

