export function SynMark({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      role="img"
    >
      <circle cx="12" cy="13" r="5.4" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="13" r="1.9" fill="currentColor" />
      <path d="M5 6.5 L9 10.5 M19 6.5 L15 10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="5" cy="6.5" r="1.5" fill="currentColor" />
      <circle cx="19" cy="6.5" r="1.5" fill="currentColor" />
    </svg>
  );
}
