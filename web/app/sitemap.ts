import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/** Only the landing page is meant to be indexed: the quiz and weak-spots
 * routes are per-session state behind a guest id and say nothing useful
 * to a crawler. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: `${SITE_URL}/`, changeFrequency: "weekly", priority: 1 }];
}
