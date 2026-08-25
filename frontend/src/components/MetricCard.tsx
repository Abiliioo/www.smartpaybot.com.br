type MetricCardProps = {
  label: string
  value: string
  detail: string
  tone?: 'blue' | 'green' | 'amber' | 'neutral'
}

export function MetricCard({ label, value, detail, tone = 'neutral' }: MetricCardProps) {
  return (
    <div className={`spb-metric spb-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  )
}
