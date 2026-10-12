// A simple card back in the classic style: dark field with a solid dark brown oval in the
// middle. Drawn from scratch as SVG (no Konami artwork), so it's sharp at any size.

export function CardBack({ className = "" }: { className?: string }) {
  return (
    <svg className={`card-back ${className}`} viewBox="0 0 590 860" preserveAspectRatio="none"
         role="img" aria-label="Card back">
      <rect width="590" height="860" rx="22" fill="#4a2e14" />
      <rect x="26" y="26" width="538" height="808" rx="10" fill="#1a0f07" />
      <ellipse cx="295" cy="430" rx="160" ry="225" fill="#5a3315" />
    </svg>
  );
}
