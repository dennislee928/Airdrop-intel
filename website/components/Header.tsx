'use client'

import { motion } from 'framer-motion'

interface HeaderProps {
  lastUpdate: string
}

export default function Header({ lastUpdate }: Readonly<HeaderProps>) {
  return (
    <header className="pixel-border bg-[var(--bg-secondary)] p-6 mb-8">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, type: 'spring' }}
        className="text-center"
      >
        <h1 className="text-4xl md:text-6xl mb-4 pixel-text text-[var(--pixel-cyan)]">
          🎮 AIRDROP INTEL
        </h1>
        <p className="text-xs md:text-sm text-[var(--pixel-yellow)] blink">
          ⚡ REAL-TIME AIRDROP INTELLIGENCE DASHBOARD ⚡
        </p>
        {lastUpdate && (
          <p className="text-xs mt-2 text-[var(--pixel-gray)]">
            Last Update: {lastUpdate}
          </p>
        )}
      </motion.div>
    </header>
  )
}

