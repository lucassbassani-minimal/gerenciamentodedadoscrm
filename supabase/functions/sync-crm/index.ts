/**
 * Edge Function: sync-crm
 * Ingestão incremental de Shopify, Klaviyo e Google Sheets → Supabase
 *
 * Segredos necessários (Supabase Dashboard → Settings → Edge Functions):
 *   KLAVIYO_PRIVATE_API_KEY
 *   SHOPIFY_SHEETS_CSV_URL
 *   GOOGLE_SHEETS_CSV_URL
 */
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// ── Constantes ─────────────────────────────────────────────────────────────

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const KLAVIYO_BASE = "https://a.klaviyo.com/api";
const KLAVIYO_REVISION = "2024-10-15";
const CAMPAIGNS_SINCE = "2026-02-01T00:00:00+00:00";
const SHOPIFY_BUFFER_DAYS = 2;
const SHOPIFY_LOOKBACK_DAYS = 60;

const UTM_TO_SLUG: Record<string, string> = {
  "email|email_fluxo": "email_flow",
  "email|fluxos_crm": "email_flow",
  "email|email_campanha": "email_campaign",
  "whatsapp|whatsapp_fluxo": "wpp_flow",
  "whatsapp|whatsapp_fluxo_ia": "wpp_flow",
  "whatsapp|fluxos_crm": "wpp_flow",
  "whatsapp|whatsapp_campanha": "wpp_campaign",
  "whatsapp|comunidade": "wpp_community",
  "email|flow": "email_flow",
  "email|campaign": "email_campaign",
  "whatsapp|flow": "wpp_flow",
  "whatsapp|campaign": "wpp_campaign",
  "community|": "wpp_community",
};

const CHANNEL_SLUG_MAP: Record<string, string> = {
  "Email Fluxo": "email_flow",
  "Email Campanha": "email_campaign",
  "Email Care": "email_campaign",
  "Whatsapp Fluxo": "wpp_flow",
  "Whatsapp Campanha": "wpp_campaign",
  "Whatsapp": "wpp_community",
};

const METRIC_FIELDS: Record<string, string> = {
  sends: "Received Email",
  opens: "Opened Email",
  clicks: "Clicked Email",
  bounces: "Bounced Email",
  spam_complaints: "Marked Email as Spam",
  unsubscribes: "Unsubscribed from Email Marketing",
};

const EMAIL_ACTION_TYPES = new Set(["SEND_EMAIL", "EMAIL"]);
const ACTIVE_CAMPAIGN_STATUSES = new Set(["Sent", "Sending", "Scheduled"]);

// ── Utilidades ─────────────────────────────────────────────────────────────

const nowIso = () => new Date().toISOString();

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setUTCDate(r.getUTCDate() + n);
  return r;
}

function todayDate(): Date {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === "," && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

function parseBrDecimal(raw: string): number {
  return parseFloat((raw || "0").replace(/\./g, "").replace(",", ".")) || 0;
}

// ── Klaviyo HTTP ───────────────────────────────────────────────────────────

async function klaviyoGet(path: string, params: Record<string, string>, key: string): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 300));
  const url = new URL(path.startsWith("http") ? path : `${KLAVIYO_BASE}${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(url.toString(), {
      headers: { Authorization: `Klaviyo-API-Key ${key}`, revision: KLAVIYO_REVISION },
    });
    if (res.status === 429) {
      const wait = (parseInt(res.headers.get("Retry-After") ?? "5") + 1) * 1000;
      console.log(`Klaviyo 429 em ${path} — aguardando ${wait}ms`);
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    if (!res.ok) throw new Error(`Klaviyo GET ${path} → ${res.status}: ${await res.text()}`);
    return res.json();
  }
  throw new Error(`Klaviyo GET ${path} → 429 após 4 tentativas`);
}

async function klaviyoPost(path: string, body: unknown, key: string): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 300));
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(`${KLAVIYO_BASE}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Klaviyo-API-Key ${key}`,
        revision: KLAVIYO_REVISION,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (res.status === 429) {
      const wait = (parseInt(res.headers.get("Retry-After") ?? "5") + 1) * 1000;
      console.log(`Klaviyo 429 em ${path} — aguardando ${wait}ms`);
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    if (!res.ok) throw new Error(`Klaviyo POST ${path} → ${res.status}: ${await res.text()}`);
    return res.json();
  }
  throw new Error(`Klaviyo POST ${path} → 429 após 4 tentativas`);
}

async function* klaviyoPaginate(path: string, params: Record<string, string>, key: string) {
  // deno-lint-ignore no-explicit-any
  let body = (await klaviyoGet(path, params, key)) as any;
  yield* body.data ?? [];
  let next = body.links?.next;
  while (next) {
    body = (await klaviyoGet(next, {}, key)) as any;
    yield* body.data ?? [];
    next = body.links?.next;
  }
}

// ── DB helpers ─────────────────────────────────────────────────────────────

async function getChannelIds(sb: SupabaseClient): Promise<Record<string, string>> {
  const { data } = await sb.from("dim_channels").select("id,slug");
  return Object.fromEntries((data ?? []).map((r: { slug: string; id: string }) => [r.slug, r.id]));
}

async function getAssetMap(sb: SupabaseClient): Promise<Record<string, string>> {
  const { data } = await sb.from("dim_assets").select("id,external_id").eq("source_tool", "klaviyo").limit(10000);
  return Object.fromEntries((data ?? []).map((r: { external_id: string; id: string }) => [r.external_id, r.id]));
}

async function getAssetItemMap(sb: SupabaseClient): Promise<Record<string, string>> {
  const { data } = await sb.from("dim_asset_items").select("id,external_id").eq("type", "email").limit(10000);
  return Object.fromEntries((data ?? []).map((r: { external_id: string; id: string }) => [r.external_id, r.id]));
}

async function getSyncedCampaignIds(sb: SupabaseClient): Promise<Set<string>> {
  const { data: items } = await sb.from("dim_asset_items").select("asset_id").eq("type", "email").limit(10000);
  const assetIds = [...new Set((items ?? []).map((r: { asset_id: string }) => r.asset_id))];
  if (!assetIds.length) return new Set();
  const { data: assets } = await sb.from("dim_assets").select("external_id")
    .eq("type", "campaign").eq("source_tool", "klaviyo").in("id", assetIds).limit(10000);
  return new Set((assets ?? []).map((r: { external_id: string }) => r.external_id));
}

async function getSyncedFlowIds(sb: SupabaseClient): Promise<Set<string>> {
  const { data: items } = await sb.from("dim_asset_items").select("asset_id").eq("type", "email").limit(10000);
  const assetIds = [...new Set((items ?? []).map((r: { asset_id: string }) => r.asset_id))];
  if (!assetIds.length) return new Set();
  const { data: assets } = await sb.from("dim_assets").select("external_id")
    .eq("type", "flow").eq("source_tool", "klaviyo").in("id", assetIds).limit(10000);
  return new Set((assets ?? []).map((r: { external_id: string }) => r.external_id));
}

async function getLatestDates(sb: SupabaseClient) {
  const latest = async (table: string, col: string): Promise<Date | null> => {
    const { data } = await sb.from(table).select(col).order(col, { ascending: false }).limit(1);
    const raw = (data as Record<string, string>[] | null)?.[0]?.[col];
    return raw ? new Date(String(raw).slice(0, 10) + "T00:00:00Z") : null;
  };
  return {
    orders: await latest("fact_orders", "order_date"),
    emailSends: await latest("fact_email_sends", "date"),
  };
}

// ── Shopify ────────────────────────────────────────────────────────────────

async function syncShopify(
  sb: SupabaseClient,
  channelIds: Record<string, string>,
  since: Date,
): Promise<{ count: number }> {
  const csvUrl = Deno.env.get("SHOPIFY_SHEETS_CSV_URL")!;
  const res = await fetch(csvUrl, { redirect: "follow" });
  if (!res.ok) throw new Error(`Shopify CSV → ${res.status}`);
  const text = await res.text();

  const lines = text.split("\n");
  const headers = parseCSVLine(lines[0]).map((h) => h.trim().replace(/^"|"$/g, ""));

  const records = [];
  const seenIds: Record<string, number> = {};

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const cols = parseCSVLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => (row[h] = (cols[idx] ?? "").trim().replace(/^"|"$/g, "")));

    if ((row.financial_status ?? "").toUpperCase() !== "PAID") continue;

    const parts = (row.processed_at_data ?? "").split("/");
    if (parts.length !== 3) continue;
    const orderDate = new Date(Date.UTC(+parts[2], +parts[1] - 1, +parts[0]));
    if (isNaN(orderDate.getTime()) || orderDate < since) continue;

    const baseId = `${orderDate.toISOString().slice(0, 10)}_${row.processed_at_hora ?? ""}`;
    const count = seenIds[baseId] ?? 0;
    seenIds[baseId] = count + 1;
    const orderId = count === 0 ? baseId : `${baseId}_${count}`;

    const revenue = parseBrDecimal(row.net_revenue ?? "0");
    if (revenue <= 0) continue;

    const slug = UTM_TO_SLUG[`${row.utm_source ?? ""}|${row.utm_medium ?? ""}`];
    records.push({
      order_id: orderId,
      order_date: orderDate.toISOString().slice(0, 10),
      revenue_brl: revenue.toFixed(2),
      is_first_purchase: (row.customer_type ?? "") === "Primeira Compra",
      utm_source: row.utm_source || null,
      utm_medium: row.utm_medium || null,
      utm_campaign: row.utm_campaign || null,
      attributed_channel_id: slug ? (channelIds[slug] ?? null) : null,
      data_source: "shopify",
      ingested_at: nowIso(),
    });
  }

  if (records.length > 0) {
    await sb.from("fact_orders").upsert(records, { onConflict: "order_id" });
  }
  console.log(`Shopify: ${records.length} pedidos`);
  return { count: records.length };
}

// ── Klaviyo ────────────────────────────────────────────────────────────────

async function syncKlaviyo(
  sb: SupabaseClient,
  channelIds: Record<string, string>,
  metricsSince: Date,
): Promise<{ flows: number; campaigns: number; metrics: number }> {
  const key = Deno.env.get("KLAVIYO_PRIVATE_API_KEY")!;
  const now = nowIso();

  // 1. Fluxos
  const flows: { id: string; name: string; status: string }[] = [];
  for await (const item of klaviyoPaginate("/flows/", {
    "fields[flow]": "name,status",
    "filter": "equals(archived,false)",
    "page[size]": "50",
  }, key)) {
    // deno-lint-ignore no-explicit-any
    const a = (item as any).attributes;
    flows.push({ id: (item as any).id, name: a.name, status: a.status });
  }
  if (flows.length) {
    await sb.from("dim_assets").upsert(
      flows.map((f) => ({
        external_id: f.id,
        channel_id: channelIds["email_flow"],
        name: f.name,
        type: "flow",
        is_active: f.status === "live",
        source_tool: "klaviyo",
        updated_at: now,
        ingested_at: now,
      })),
      { onConflict: "external_id,source_tool" },
    );
  }

  // 2. Campanhas
  const campaigns: { id: string; name: string; status: string }[] = [];
  for await (const item of klaviyoPaginate("/campaigns/", {
    "fields[campaign]": "name,status,created_at,send_time",
    "filter": `equals(messages.channel,'email'),greater-or-equal(created_at,${CAMPAIGNS_SINCE})`,
  }, key)) {
    // deno-lint-ignore no-explicit-any
    const a = (item as any).attributes;
    campaigns.push({ id: (item as any).id, name: a.name, status: a.status });
  }
  if (campaigns.length) {
    await sb.from("dim_assets").upsert(
      campaigns.map((c) => ({
        external_id: c.id,
        channel_id: channelIds["email_campaign"],
        name: c.name,
        type: "campaign",
        is_active: ACTIVE_CAMPAIGN_STATUSES.has(c.status),
        source_tool: "klaviyo",
        updated_at: now,
        ingested_at: now,
      })),
      { onConflict: "external_id,source_tool" },
    );
  }

  const assetMap = await getAssetMap(sb);

  // 3. Mensagens de fluxo (pula fluxos já sincronizados — mudam raramente)
  const syncedFlowIds = await getSyncedFlowIds(sb);
  for (const flow of flows) {
    if (syncedFlowIds.has(flow.id)) continue;
    const assetId = assetMap[flow.id];
    if (!assetId) continue;
    let emailPos = 0;
    const msgRecords = [];
    for await (const action of klaviyoPaginate(`/flows/${flow.id}/flow-actions/`, { "fields[flow-action]": "action_type" }, key)) {
      // deno-lint-ignore no-explicit-any
      if (!EMAIL_ACTION_TYPES.has((action as any).attributes?.action_type)) continue;
      emailPos++;
      for await (const msg of klaviyoPaginate(`/flow-actions/${(action as any).id}/flow-messages/`, { "fields[flow-message]": "name,created,updated" }, key)) {
        // deno-lint-ignore no-explicit-any
        const ma = (msg as any).attributes;
        msgRecords.push({
          external_id: (msg as any).id,
          asset_id: assetId,
          name: ma?.name || `Email ${emailPos}`,
          type: "email",
          position: emailPos,
          updated_at: now,
          ingested_at: now,
        });
      }
    }
    if (msgRecords.length) {
      await sb.from("dim_asset_items").upsert(msgRecords, { onConflict: "external_id,type" });
    }
  }

  // 4. Mensagens de campanha (pula campanhas já sincronizadas)
  const syncedCampaignIds = await getSyncedCampaignIds(sb);
  for (const campaign of campaigns) {
    if (syncedCampaignIds.has(campaign.id)) continue;
    const assetId = assetMap[campaign.id];
    if (!assetId) continue;
    const msgRecords = [];
    for await (const msg of klaviyoPaginate(`/campaigns/${campaign.id}/campaign-messages/`, { "fields[campaign-message]": "label,created_at,updated_at" }, key)) {
      // deno-lint-ignore no-explicit-any
      const ma = (msg as any).attributes;
      msgRecords.push({
        external_id: (msg as any).id,
        asset_id: assetId,
        name: ma?.label || "Campaign Email",
        type: "email",
        position: null,
        updated_at: now,
        ingested_at: now,
      });
    }
    if (msgRecords.length) {
      await sb.from("dim_asset_items").upsert(msgRecords, { onConflict: "external_id,type" });
    }
  }

  // 5. Métricas de e-mail (só desde a última data no banco)
  let metricsCount = 0;
  const today = todayDate();
  if (metricsSince <= today) {
    const metricIds: Record<string, string> = {};
    const targetNames = new Set(Object.values(METRIC_FIELDS));
    for await (const item of klaviyoPaginate("/metrics/", { "fields[metric]": "name" }, key)) {
      // deno-lint-ignore no-explicit-any
      const name = (item as any).attributes?.name;
      // deno-lint-ignore no-explicit-any
      if (targetNames.has(name)) metricIds[name] = (item as any).id;
    }

    const rows: Record<string, Record<string, number | string>> = {};
    const sinceStr = metricsSince.toISOString().slice(0, 10);
    const untilStr = today.toISOString().slice(0, 10);

    for (const [field, metricName] of Object.entries(METRIC_FIELDS)) {
      const metricId = metricIds[metricName];
      if (!metricId) continue;
      // deno-lint-ignore no-explicit-any
      const result = (await klaviyoPost("/metric-aggregates/", {
        data: {
          type: "metric-aggregate",
          attributes: {
            metric_id: metricId,
            measurements: ["count"],
            interval: "day",
            page_size: 500,
            filter: [
              `greater-or-equal(datetime,${sinceStr}T00:00:00+00:00)`,
              `less-than(datetime,${untilStr}T23:59:59+00:00)`,
            ],
            by: ["$message"],
          },
        },
      }, key)) as any;

      const attrs = result.data?.attributes ?? {};
      const dates: string[] = (attrs.dates ?? []).map((d: string) => d.slice(0, 10));
      for (const row of attrs.data ?? []) {
        const msgId = row.dimensions?.[0];
        ((row.measurements?.count ?? []) as number[]).forEach((count, i) => {
          if (!count || i >= dates.length) return;
          const k = `${msgId}|${dates[i]}`;
          if (!rows[k]) {
            rows[k] = { message_id: msgId, date: dates[i], sends: 0, opens: 0, clicks: 0, bounces: 0, spam_complaints: 0, unsubscribes: 0 };
          }
          rows[k][field] = (rows[k][field] as number) + count;
        });
      }
    }

    const itemMap = await getAssetItemMap(sb);
    const metricRecords = [];
    for (const row of Object.values(rows)) {
      const itemId = itemMap[row.message_id as string];
      if (!itemId) continue;
      metricRecords.push({
        date: row.date,
        asset_item_id: itemId,
        sends: row.sends,
        opens: row.opens,
        clicks: row.clicks,
        bounces: row.bounces,
        spam_complaints: row.spam_complaints,
        unsubscribes: row.unsubscribes,
        ingested_at: now,
      });
    }

    for (let i = 0; i < metricRecords.length; i += 500) {
      await sb.from("fact_email_sends").upsert(metricRecords.slice(i, i + 500), { onConflict: "date,asset_item_id" });
    }
    metricsCount = metricRecords.length;
  }

  // 6. Formulários
  const formRecords = [];
  for await (const item of klaviyoPaginate("/forms/", { "fields[form]": "name,status,form_type,created_at,updated_at" }, key)) {
    // deno-lint-ignore no-explicit-any
    const a = (item as any).attributes;
    if ((a?.status ?? "").toLowerCase() === "archived") continue;
    formRecords.push({
      external_id: (item as any).id,
      name: a.name,
      type: a.form_type?.toLowerCase() ?? "form",
      is_active: !["draft", "archived"].includes((a.status ?? "").toLowerCase()),
      ingested_at: now,
    });
  }
  if (formRecords.length) {
    await sb.from("dim_forms").upsert(formRecords, { onConflict: "external_id" });
  }

  console.log(`Klaviyo: ${flows.length} fluxos, ${campaigns.length} campanhas, ${metricsCount} linhas de métricas`);
  return { flows: flows.length, campaigns: campaigns.length, metrics: metricsCount };
}

// ── Google Sheets ──────────────────────────────────────────────────────────

async function syncSheets(
  sb: SupabaseClient,
  channelIds: Record<string, string>,
): Promise<{ sessions: number; utm: number }> {
  const csvUrl = Deno.env.get("GOOGLE_SHEETS_CSV_URL")!;
  const res = await fetch(csvUrl, { redirect: "follow" });
  if (!res.ok) throw new Error(`Sheets CSV → ${res.status}`);
  const text = await res.text();
  const now = nowIso();

  const lines = text.split("\n");
  const headers = parseCSVLine(lines[0]).map((h) => h.trim().replace(/^"|"$/g, ""));

  const channelTotals: Record<string, { date: string; slug: string; sessions: number; atc: number; bco: number; orders: number; revenue: number }> = {};
  const utmTotals: Record<string, { date: string; slug: string; utm_source: string; utm_medium: string; utm_campaign: string; utm_term: string; utm_content: string; sessions: number; atc: number; bco: number; orders: number; revenue: number }> = {};

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const cols = parseCSVLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => (row[h] = (cols[idx] ?? "").trim().replace(/^"|"$/g, "")));

    const slug = CHANNEL_SLUG_MAP[row.agrupamento_custom_Minimal ?? ""];
    if (!slug) continue;

    const parts = (row.event_date ?? "").split("/");
    if (parts.length !== 3) continue;
    const rowDate = `${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;

    const sessions = parseInt(row.sessoes) || 0;
    const atc = parseInt(row.add_to_cart) || 0;
    const bco = parseInt(row.begin_checkout) || 0;
    const orders = parseInt(row.purchase) || 0;
    const revenue = parseBrDecimal(row.revenue ?? "0");

    const chanKey = `${rowDate}|${slug}`;
    if (!channelTotals[chanKey]) channelTotals[chanKey] = { date: rowDate, slug, sessions: 0, atc: 0, bco: 0, orders: 0, revenue: 0 };
    channelTotals[chanKey].sessions += sessions;
    channelTotals[chanKey].atc += atc;
    channelTotals[chanKey].bco += bco;
    channelTotals[chanKey].orders += orders;
    channelTotals[chanKey].revenue += revenue;

    const srcMed = (row.source_medium ?? "").split("/").map((s) => s.trim());
    const utm_source = srcMed[0] ?? "";
    const utm_medium = srcMed[1] ?? "";
    const utm_campaign = row.campaign ?? "";
    const utm_term = row.term ?? "";
    const utm_content = row.content ?? "";
    const utmKey = `${rowDate}|${slug}|${utm_source}|${utm_medium}|${utm_campaign}|${utm_term}|${utm_content}`;
    if (!utmTotals[utmKey]) utmTotals[utmKey] = { date: rowDate, slug, utm_source, utm_medium, utm_campaign, utm_term, utm_content, sessions: 0, atc: 0, bco: 0, orders: 0, revenue: 0 };
    utmTotals[utmKey].sessions += sessions;
    utmTotals[utmKey].atc += atc;
    utmTotals[utmKey].bco += bco;
    utmTotals[utmKey].orders += orders;
    utmTotals[utmKey].revenue += revenue;
  }

  const sessionRecords = Object.values(channelTotals)
    .filter((r) => channelIds[r.slug])
    .map((r) => ({
      date: r.date,
      channel_id: channelIds[r.slug],
      sessions: r.sessions,
      add_to_cart: Math.min(r.atc, r.sessions),
      begin_checkout: Math.min(r.bco, Math.min(r.atc, r.sessions)),
      orders: r.orders,
      revenue_brl: r.revenue.toFixed(2),
      ingested_at: now,
    }));

  if (sessionRecords.length) {
    await sb.from("fact_sessions").upsert(sessionRecords, { onConflict: "date,channel_id" });
  }

  const utmRecords = Object.values(utmTotals)
    .filter((r) => channelIds[r.slug])
    .map((r) => ({
      date: r.date,
      channel_id: channelIds[r.slug],
      utm_source: r.utm_source,
      utm_medium: r.utm_medium,
      utm_campaign: r.utm_campaign,
      utm_term: r.utm_term,
      utm_content: r.utm_content,
      sessions: r.sessions,
      add_to_cart: Math.min(r.atc, r.sessions),
      begin_checkout: Math.min(r.bco, Math.min(r.atc, r.sessions)),
      orders: r.orders,
      revenue_brl: r.revenue.toFixed(2),
      ingested_at: now,
    }));

  for (let i = 0; i < utmRecords.length; i += 1000) {
    await sb.from("fact_sessions_utm").upsert(utmRecords.slice(i, i + 1000), {
      onConflict: "date,channel_id,utm_source,utm_medium,utm_campaign,utm_term,utm_content",
    });
  }

  console.log(`Sheets: ${sessionRecords.length} sessões, ${utmRecords.length} UTM`);
  return { sessions: sessionRecords.length, utm: utmRecords.length };
}

// ── Handler principal ──────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  try {
    const required = ["KLAVIYO_PRIVATE_API_KEY", "SHOPIFY_SHEETS_CSV_URL", "GOOGLE_SHEETS_CSV_URL"];
    const missing = required.filter((v) => !Deno.env.get(v));
    if (missing.length) {
      return new Response(
        JSON.stringify({ status: "error", message: `Segredos não configurados no Supabase: ${missing.join(", ")}` }),
        { status: 500, headers: { ...CORS, "Content-Type": "application/json" } },
      );
    }

    const sb = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const [channelIds, latestDates] = await Promise.all([
      getChannelIds(sb),
      getLatestDates(sb),
    ]);

    // Shopify: desde MAX(order_date) - 2 dias, máximo 60 dias atrás
    const today = todayDate();
    let shopifySince: Date;
    if (latestDates.orders) {
      shopifySince = addDays(latestDates.orders, -SHOPIFY_BUFFER_DAYS);
      const maxBack = addDays(today, -SHOPIFY_LOOKBACK_DAYS);
      if (shopifySince < maxBack) shopifySince = maxBack;
    } else {
      shopifySince = addDays(today, -SHOPIFY_LOOKBACK_DAYS);
    }

    // Klaviyo métricas: desde MAX(date) + 1 dia, máximo 7 dias atrás
    let metricsSince: Date;
    if (latestDates.emailSends) {
      metricsSince = addDays(latestDates.emailSends, 1);
    } else {
      metricsSince = addDays(today, -7);
    }
    const metricsFloor = addDays(today, -7);
    if (metricsSince < metricsFloor) metricsSince = metricsFloor;

    // Rodar em sequência para não estourar memória
    const shopifyResult = await syncShopify(sb, channelIds, shopifySince);
    const sheetsResult = await syncSheets(sb, channelIds);
    const klaviyoResult = await syncKlaviyo(sb, channelIds, metricsSince);

    return new Response(
      JSON.stringify({ status: "ok", shopify: shopifyResult, sheets: sheetsResult, klaviyo: klaviyoResult }),
      { headers: { ...CORS, "Content-Type": "application/json" } },
    );
  } catch (err) {
    console.error(err);
    return new Response(
      JSON.stringify({ status: "error", message: String(err) }),
      { status: 500, headers: { ...CORS, "Content-Type": "application/json" } },
    );
  }
});
