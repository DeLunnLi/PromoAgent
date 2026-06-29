const DDG_HTML_URL = 'https://html.duckduckgo.com/html/';
const DDG_INSTANT_URL = 'https://api.duckduckgo.com/';

export async function webSearch(query, options = {}) {
  const q = String(query ?? '').trim();
  if (!q) {
    throw new Error('web_search requires a non-empty query.');
  }

  const maxResults = Math.min(Math.max(Number(options.maxResults ?? 5), 1), 10);
  const results = [];

  try {
    const instant = await fetchInstantAnswer(q);
    if (instant) results.push(instant);
  } catch {
    // Instant API is best-effort.
  }

  try {
    const htmlResults = await fetchHtmlResults(q, maxResults);
    for (const item of htmlResults) {
      if (results.some((existing) => existing.url === item.url)) continue;
      results.push(item);
      if (results.length >= maxResults) break;
    }
  } catch (error) {
    if (results.length === 0) {
      throw error;
    }
  }

  return {
    query: q,
    results: results.slice(0, maxResults)
  };
}

async function fetchInstantAnswer(query) {
  const url = `${DDG_INSTANT_URL}?q=${encodeURIComponent(query)}&format=json&no_html=1&skip_disambig=1`;
  const response = await fetch(url, {
    headers: { 'User-Agent': 'source2launch/0.2 (+https://github.com/DeLunnLi/star_up)' }
  });

  if (!response.ok) return null;

  const data = await response.json();
  const abstract = String(data.AbstractText ?? data.Abstract ?? '').trim();
  if (!abstract) return null;

  return {
    title: String(data.Heading ?? query).trim(),
    url: String(data.AbstractURL ?? data.Results?.[0]?.FirstURL ?? '').trim() || null,
    snippet: abstract.slice(0, 500),
    source: 'duckduckgo-instant'
  };
}

async function fetchHtmlResults(query, maxResults) {
  const body = new URLSearchParams({ q: query, kl: 'cn-zh' });
  const response = await fetch(DDG_HTML_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': 'source2launch/0.2 (+https://github.com/DeLunnLi/star_up)'
    },
    body
  });

  if (!response.ok) {
    throw new Error(`Web search failed (${response.status})`);
  }

  const html = await response.text();
  const results = [];
  const blockPattern = /<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>[\s\S]*?<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)<\/a>/gi;

  for (const match of html.matchAll(blockPattern)) {
    const url = decodeRedirectUrl(match[1]);
    const title = stripHtml(match[2]);
    const snippet = stripHtml(match[3]);
    if (!url || !title) continue;
    results.push({ title, url, snippet: snippet.slice(0, 400), source: 'duckduckgo-html' });
    if (results.length >= maxResults) break;
  }

  return results;
}

export async function fetchPageText(url, options = {}) {
  const target = String(url ?? '').trim();
  if (!/^https?:\/\//i.test(target)) {
    throw new Error('fetch_page_text requires an http(s) URL.');
  }

  const maxChars = Math.min(Math.max(Number(options.maxChars ?? 4_000), 500), 12_000);
  const response = await fetch(target, {
    headers: { 'User-Agent': 'source2launch/0.2 (+https://github.com/DeLunnLi/star_up)' },
    redirect: 'follow'
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch page (${response.status})`);
  }

  const contentType = String(response.headers.get('content-type') ?? '');
  const raw = (await response.text()).slice(0, maxChars * 4);
  const text = contentType.includes('html') ? htmlToText(raw) : raw;
  return {
    url: target,
    contentType,
    text: text.slice(0, maxChars)
  };
}

function decodeRedirectUrl(raw) {
  const value = String(raw ?? '').trim();
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;

  try {
    const parsed = new URL(value, 'https://duckduckgo.com');
    const uddg = parsed.searchParams.get('uddg');
    if (uddg) return decodeURIComponent(uddg);
  } catch {
    return value;
  }

  return value;
}

function stripHtml(value) {
  return String(value ?? '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim();
}

function htmlToText(html) {
  return stripHtml(
    html
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<\/(p|div|h[1-6]|li|br|tr)>/gi, '\n')
  );
}
