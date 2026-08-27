import { Button } from './Button'
import { Card } from './Card'
import { Pill } from './Pill'

type PlanCardProps = {
  name: string
  price: string
  caption: string
  features: string[]
  featured?: boolean
  cta: string
  href?: string
  onClick?: () => void
}

export function PlanCard({ name, price, caption, features, featured = false, cta, href, onClick }: PlanCardProps) {
  return (
    <Card tone={featured ? 'accent' : 'default'} className="spb-plan-card">
      <div className="spb-plan-card__top">
        <div>
          <span>{name}</span>
          <strong>{price}</strong>
          <small>{caption}</small>
        </div>
        {featured && <Pill tone="blue">Mais valor</Pill>}
      </div>
      <ul>
        {features.map((feature) => (
          <li key={feature}>{feature}</li>
        ))}
      </ul>
      <Button variant={featured ? 'primary' : 'secondary'} href={href} onClick={onClick}>
        {cta}
      </Button>
    </Card>
  )
}
