'use client'

import { motion } from 'framer-motion'

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

interface AirdropCardProps {
  event: AirdropEvent
  alertPriority: 'high' | 'medium' | 'low' | null
}

export default function AirdropCard({ event, alertPriority }: AirdropCardProps) {
  const statusColors = {
    active: 'var(--pixel-green)',
    upcoming: 'var(--pixel-yellow)',
    ended: 'var(--pixel-gray)',
    potential: 'var(--pixel-cyan)',
  }

  const priorityColors = {
    high: 'var(--pixel-red)',
    medium: 'var(--pixel-yellow)',
    low: 'var(--pixel-cyan)',
  }

  return (
    <motion.div
      whileHover={{ scale: 1.05, y: -4 }}
      className="pixel-card cursor-pointer"
    >
      {alertPriority && (
        <div
          className="text-xs mb-2 blink pixel-text"
          style={{ color: priorityColors[alertPriority] }}
        >
          ⚠️ {alertPriority.toUpperCase()} PRIORITY
        </div>
      )}

      <h3 className="text-lg mb-2 pixel-text text-[var(--pixel-white)]">
        {event.project}
      </h3>

      <div className="flex items-center gap-2 mb-3">
        <span
          className="text-xs px-2 py-1 pixel-border"
          style={{
            color: statusColors[event.status],
            borderColor: statusColors[event.status],
          }}
        >
          {event.status.toUpperCase()}
        </span>
        <span className="text-xs opacity-70">
          {event.source}
        </span>
      </div>

      {event.reward_type && (
        <div className="text-xs mb-2 opacity-70">
          Reward: {event.reward_type}
        </div>
      )}

      {event.requirements && event.requirements.length > 0 && (
        <div className="text-xs mb-2 opacity-70">
          Requirements: {event.requirements.length} task(s)
        </div>
      )}

      {event.deadline && (
        <div className="text-xs mb-2 text-[var(--pixel-yellow)]">
          Deadline: {new Date(event.deadline).toLocaleDateString()}
        </div>
      )}

      {event.links?.details && (
        <a
          href={event.links.details}
          target="_blank"
          rel="noopener noreferrer"
          className="pixel-button text-xs mt-4 block text-center"
          onClick={(e) => e.stopPropagation()}
        >
          VIEW DETAILS →
        </a>
      )}
    </motion.div>
  )
}

