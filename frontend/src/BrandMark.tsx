interface BrandMarkProps {
  size?: number;
}

export function BrandMark({ size = 26 }: BrandMarkProps) {
  return (
    <span className="brandmark">
      <span className="brandmark-box" style={{ width: size, height: size }} aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
          width={Math.round(size * 0.55)}
          height={Math.round(size * 0.55)}
        >
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <circle cx="9" cy="10" r="1.6" />
          <path d="M5 19l5-5 4 4 3-3 2 2" />
        </svg>
      </span>
      <span className="brandmark-word">syn</span>
    </span>
  );
}
