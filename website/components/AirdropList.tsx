'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import AirdropCard from './AirdropCard'

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

interface Alert {
  project: string
  priority: 'high' | 'medium' | 'low'
}

interface AirdropListProps {
  events: AirdropEvent[]
  alerts: Alert[]
}

export default function AirdropList({ events, alerts }: AirdropListProps) {
  const [filter, setFilter] = useState<'all' | 'active' | 'upcoming' | 'ended' | 'potential'>('all')
  const [sortBy, setSortBy] = useState<'name' | 'status' | 'source'>('name')

  const filteredEvents = events.filter(event => {
    if (filter === 'all') return true
    return event.status === filter
  })

  const sortedEvents = [...filteredEvents].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.project.localeCompare(b.project)
      case 'status':
        return a.status.localeCompare(b.status)
      case 'source':
        return a.source.localeCompare(b.source)
      default:
        return 0
    }
  })

  const getAlertPriority = (project: string): 'high' | 'medium' | 'low' | null => {
    const alert = alerts.find(a => a.project === project)
    return alert?.priority || null
  }

  return (
    <div className="pixel-border bg-[var(--bg-secondary)] p-6">
      <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
        <h2 className="text-2xl pixel-text text-[var(--pixel-white)]">
          🎯 AIRDROP LIST ({sortedEvents.length})
        </h2>
        
        <div className="flex flex-wrap gap-2">
          {(['all', 'active', 'upcoming', 'ended', 'potential'] as const).map(status => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`pixel-button text-xs ${
                filter === status ? 'bg-[var(--pixel-yellow)]' : ''
              }`}
            >
              {status.toUpperCase()}
            </button>
          ))}
        </div>

        <select
          onChange={(e) => setSortBy(e.target.value as any)}
          className="pixel-button text-xs"
          style={{ fontFamily: 'inherit' }}
        >
          <option value="name">Sort: Name</option>
          <option value="status">Sort: Status</option>
          <option value="source">Sort: Source</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <AnimatePresence>
          {sortedEvents.map((event, index) => (
            <motion.div
              key={`${event.project}-${event.source}-${index}`}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ delay: index * 0.05 }}
            >
              <AirdropCard
                event={event}
                alertPriority={getAlertPriority(event.project)}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {sortedEvents.length === 0 && (
        <div className="text-center py-12">
          <p className="text-xl text-[var(--pixel-gray)] pixel-text">
            NO AIRDROPS FOUND
          </p>
        </div>
      )}
    </div>
  )
}

