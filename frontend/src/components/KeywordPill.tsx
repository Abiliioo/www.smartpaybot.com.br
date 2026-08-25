type KeywordPillProps = {
  label: string
}

export function KeywordPill({ label }: KeywordPillProps) {
  return <span className="spb-keyword-pill">{label}</span>
}
