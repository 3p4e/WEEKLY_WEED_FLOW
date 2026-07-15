import { motion, AnimatePresence } from 'framer-motion'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { Card } from '../ui/Card'

export function LivePreview() {
  const agents = useGenerationStore((s) => s.agents)
  const completedSections = agents.filter((a) => a.status === 'done' && a.content)

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-300">Live Preview</h3>
      {completedSections.length === 0 ? (
        <div className="text-sm text-slate-500 py-8 text-center">
          Content will appear here as agents complete their work...
        </div>
      ) : (
        <AnimatePresence>
          {completedSections.map((section) => (
            <motion.div
              key={section.role}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="!p-4">
                <h4 className="text-sm font-semibold text-emerald-400 mb-2">{section.label}</h4>
                <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                  {section.content}
                </div>
              </Card>
            </motion.div>
          ))}
        </AnimatePresence>
      )}
    </div>
  )
}
