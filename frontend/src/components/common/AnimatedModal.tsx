import { type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'

interface AnimatedModalProps {
  isOpen: boolean
  overlayClassName: string
  dialogClassName: string
  ariaLabel: string
  onClose: () => void
  children: ReactNode
}

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
}

const dialogVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 30 },
  visible: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.95, y: 30 },
}

export default function AnimatedModal({
  isOpen,
  overlayClassName,
  dialogClassName,
  ariaLabel,
  onClose,
  children,
}: AnimatedModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className={overlayClassName}
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={ariaLabel}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className={dialogClassName}
            onClick={(event) => event.stopPropagation()}
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
