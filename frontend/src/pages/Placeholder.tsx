import type { ReactNode } from 'react'
import { Badge, Card, EmptyState, PageHeader } from '../components/ui'

export default function Placeholder({ title, icon, phase, blurb }: {
  title: string
  icon: ReactNode
  phase: number
  blurb: string
}) {
  return (
    <>
      <PageHeader title={title} actions={<Badge>Arrives in Phase {phase}</Badge>} />
      <Card>
        <EmptyState icon={icon} title="Not built yet" body={blurb} />
      </Card>
    </>
  )
}
