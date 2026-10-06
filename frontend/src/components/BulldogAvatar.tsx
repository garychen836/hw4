// Original kawaii "squishy" bulldog mascot for the shopping assistant (hand-drawn SVG, no photos or external art).
// One round golden body, a white face patch, small floppy ears, a big black nose, simple shiny eyes, rosy cheeks,
// a tiny underbite fang (so it still reads as a bulldog), stubby paws, and a navy belly with a white "Y".

type Props = { size?: number; className?: string; title?: string }

export default function BulldogAvatar({ size = 40, className = '', title }: Props) {
  return (
    <svg
      className={`bulldog ${className}`}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}

      {/* floppy ears */}
      <path d="M26 30 C14 22 6 34 12 46 C16 40 22 37 30 38 Z" fill="#c98a2e" />
      <path d="M94 30 C106 22 114 34 108 46 C104 40 98 37 90 38 Z" fill="#c98a2e" />

      {/* one round squishy body (head and body together) */}
      <path
        d="M60 14 C90 14 108 34 108 64 C108 96 88 114 60 114 C32 114 12 96 12 64 C12 34 30 14 60 14 Z"
        fill="#f2b33d"
      />
      {/* soft shading on the lower body */}
      <path d="M14 74 C20 100 40 112 60 112 C80 112 100 100 106 74 C98 96 80 106 60 106 C40 106 22 96 14 74 Z" fill="#e3a02e" />

      {/* white face patch (a blaze up the forehead widening into the muzzle) */}
      <path
        d="M54 20 Q60 17 66 20 L68 40 C82 42 92 52 90 64 C88 76 74 80 60 80 C46 80 32 76 30 64 C28 52 38 42 52 40 Z"
        fill="#fffaf1"
      />

      {/* eyes: simple shiny kawaii eyes */}
      <g className="bulldog-eyes">
        <ellipse cx="40" cy="48" rx="6" ry="7" fill="#1d1d2b" />
        <ellipse cx="80" cy="48" rx="6" ry="7" fill="#1d1d2b" />
        <circle cx="38" cy="45" r="2.4" fill="#ffffff" />
        <circle cx="78" cy="45" r="2.4" fill="#ffffff" />
        <circle cx="42" cy="51" r="1" fill="#ffffff" />
        <circle cx="82" cy="51" r="1" fill="#ffffff" />
      </g>

      {/* rosy cheeks */}
      <ellipse cx="30" cy="62" rx="6" ry="3.6" fill="#f28c8c" opacity="0.7" />
      <ellipse cx="90" cy="62" rx="6" ry="3.6" fill="#f28c8c" opacity="0.7" />

      {/* big black nose */}
      <path d="M50 54 Q60 49 70 54 Q69 62 60 63 Q51 62 50 54 Z" fill="#231c24" />
      <ellipse cx="56" cy="54.5" rx="3" ry="1.2" fill="#ffffff" opacity="0.6" />

      {/* little smile with a jowly "w" and one underbite fang */}
      <path d="M60 63 L60 67" stroke="#231c24" strokeWidth="2" strokeLinecap="round" />
      <path d="M48 67 Q54 74 60 67 Q66 74 72 67" stroke="#231c24" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      <path d="M64.5 70.5 L66.5 64.5 L68.5 70 Z" fill="#ffffff" stroke="#e2d8cc" strokeWidth="0.5" />

      {/* navy belly with a white "Y" */}
      <ellipse cx="60" cy="96" rx="22" ry="15" fill="#00356b" />
      <text x="60" y="104" textAnchor="middle" fontFamily="Georgia, serif" fontWeight="700" fontSize="20" fill="#ffffff">
        Y
      </text>

      {/* stubby paws */}
      <ellipse cx="34" cy="106" rx="9" ry="6" fill="#fffaf1" />
      <ellipse cx="86" cy="106" rx="9" ry="6" fill="#fffaf1" />
      <path d="M31 104 L31 108 M35 104 L35 108" stroke="#e2cdb0" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M83 104 L83 108 M87 104 L87 108" stroke="#e2cdb0" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}
