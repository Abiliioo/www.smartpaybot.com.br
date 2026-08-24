export function BrandMark() {
  return (
    <a className="spb-brand-mark" href="/" aria-label="SmartPayBot inicio">
      <img
        className="spb-brand-mark__icon"
        src="/static/images/logo.svg"
        alt=""
        width="32"
        height="32"
      />
      <span className="spb-brand-mark__word">
        <span>SmartPay</span>
        <strong>Bot</strong>
      </span>
    </a>
  )
}
