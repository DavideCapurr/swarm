/**
 * Eyebrow — the SWARM section label.
 * Space Grotesk uppercase, 0.18em tracking, ash by default.
 * The leading em-dash is part of the brand cadence (see spread 13).
 */
export function Eyebrow({
  children,
  mono = false,
  className = "",
}: {
  children: React.ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={`${mono ? "eyebrow-mono" : "eyebrow"} ${className}`}>
      <span className="mr-2">—</span>
      {children}
    </div>
  );
}
