type SectionHeaderProps = {
  eyebrow?: string
  title: string
  copy?: string
}

export function SectionHeader({ eyebrow, title, copy }: SectionHeaderProps) {
  return (
    <div className="spb-section-header">
      {eyebrow && <p>{eyebrow}</p>}
      <h2>{title}</h2>
      {copy && <span>{copy}</span>}
    </div>
  )
}
