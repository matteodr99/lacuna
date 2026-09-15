/** The reading-width column the app pages use. The landing page manages
 * its own widths (a wider hero, full-bleed bands), which is why this is a
 * component the pages opt into rather than a wrapper in the layout. */
export default function Container({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-3xl px-6 ${className}`}>{children}</div>
  );
}
