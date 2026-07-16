import { motion } from 'framer-motion'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  onClick?: () => void
}

export function Card({ children, className = '', hover, onClick }: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      whileHover={hover ? { scale: 1.01 } : undefined}
      onClick={onClick}
      className={`
        rounded-xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm p-5
        ${hover ? 'cursor-pointer hover:border-slate-700 transition-colors' : ''}
        ${className}
      `}
    >
      {children}
    </motion.div>
  )
}
