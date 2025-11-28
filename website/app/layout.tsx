import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Airdrop Intel - 8-Bit Edition',
  description: 'Real-time airdrop intelligence dashboard with retro gaming style',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-TW">
      <body>{children}</body>
    </html>
  )
}

