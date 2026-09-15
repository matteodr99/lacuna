/** The public origin, for canonical URLs, Open Graph and the sitemap.
 * Vercel sets neither NEXT_PUBLIC_SITE_URL nor a stable public host on
 * its own, so the deployed origin is the default and an env var can
 * override it when the domain changes. */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://lacuna-zeta.vercel.app";
