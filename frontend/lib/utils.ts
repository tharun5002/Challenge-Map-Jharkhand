export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

const STOPWORDS = new Set([
  "the", "and", "for", "not", "with", "from", "this", "that", "have", "has", "are", "was",
  "our", "but", "you", "they", "them", "there", "here", "been", "very", "will", "would",
  "should", "could", "about", "into", "also", "only", "than", "then", "when", "what",
  "which", "who", "how", "why", "all", "any", "can", "may", "get", "got", "its", "it's",
  "है", "और", "के", "को", "में", "से", "पर", "हैं", "था", "थी", "एक", "यह", "वह",
]);

function tokenize(text: string): Set<string> {
  const normalized = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter((token) => token.length > 2 && !STOPWORDS.has(token));
  return new Set(normalized);
}

/** Token-overlap similarity in [0,1]. Mirrors the server-side cosine dedup signal. */
export function jaccardSimilarity(a: string, b: string): number {
  const left = tokenize(a);
  const right = tokenize(b);
  if (left.size === 0 || right.size === 0) return 0;
  let intersection = 0;
  left.forEach((token) => {
    if (right.has(token)) intersection += 1;
  });
  const union = left.size + right.size - intersection;
  return union === 0 ? 0 : intersection / union;
}
