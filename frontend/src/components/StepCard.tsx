type StepCardProps = {
  step: string
  title: string
  copy: string
}

export function StepCard({ step, title, copy }: StepCardProps) {
  return (
    <div className="spb-step-card">
      <span>{step}</span>
      <h3>{title}</h3>
      <p>{copy}</p>
    </div>
  )
}
