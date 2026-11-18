/*
 * Meter Vision Card for Home Assistant
 * https://github.com/leinemann/ha-meter-vision
 *
 * Dashboard card bundled with the Meter Vision integration, which serves
 * and loads it automatically (no dashboard resource needed). It only displays
 * what the integration computes: the accepted reading as a meter counter, the
 * consumption of today and yesterday, the hourly consumption of the last
 * 24 hours, the frame the AI read and the result of the last reading.
 * Every entity is discovered from the device of the configured reading sensor.
 *
 * One dependency-free file, no build step. Localized: English and Italian.
 *
 * Copyright (C) 2026 The ha-ai-meter-reader contributors
 *   (https://github.com/artech-lab/ha-ai-meter-reader, v1.0.1)
 * Copyright (C) 2026 The ha-meter-vision contributors
 *   (modified: renamed for the meter_vision integration, 2026-11-18)
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version. This program is distributed in the hope that it will be
 * useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 * Public License for more details: <https://www.gnu.org/licenses/>.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// The integration appends its manifest version to the URL of this module.
const CARD_VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const CARD_TAG = "meter-vision-card";
const EDITOR_TAG = "meter-vision-card-editor";
const INTEGRATION = "meter_vision";

const STRINGS = {
  en: {
    card_name: "Meter Vision",
    card_description:
      "Water, gas or energy meter read by AI: counter, daily consumption, hourly chart, last frame and reading result.",
    default_title: "Meter",
    r_accepted: "Accepted",
    r_unconfirmed: "Waiting for confirmation",
    r_decrease: "Rejected: lower than the reading",
    r_implausible: "Rejected: implausible jump",
    r_unreadable: "Not readable",
    r_wrong_digits: "Rejected: too many digits",
    r_error: "Error",
    r_corrected: "Set by hand",
    never: "never read",
    just_now: "just now",
    min_ago: "{n} min ago",
    h_ago: "{n} h ago",
    d_ago: "{n} d ago",
    read: "read {v}",
    reading_now: "reading now…",
    problem: "Problem",
    paused: "Paused",
    today: "Today",
    yesterday: "Yesterday",
    last_24h: "Last 24 h",
    per_hour: "per hour",
    peak: "peak {v}",
    no_data: "no data yet",
    frame: "Last frame",
    digits_read: "read {v}",
    to_confirm: "to confirm: {v}",
    confidence: "Confidence",
    read_now: "Read the meter now",
    reading: "Reading…",
    auto_on: "Automatic reading: on",
    auto_off: "Automatic reading: off",
    no_entity: "Select the reading sensor of an Meter Vision device.",
    // editor
    e_entity: "Reading sensor",
    e_name: "Title",
    e_show_counter: "Show counter",
    e_show_consumption: "Show consumption",
    e_show_chart: "Show hourly chart",
    e_show_frame: "Show last frame",
    e_show_result: "Show last result",
    e_show_buttons: "Show buttons"
  },
  it: {
    card_name: "Meter Vision",
    card_description:
      "Contatore di acqua, gas o energia letto dall'AI: totalizzatore, consumo giornaliero, grafico orario, ultimo fotogramma ed esito.",
    default_title: "Contatore",
    r_accepted: "Accettata",
    r_unconfirmed: "In attesa di conferma",
    r_decrease: "Scartata: inferiore alla lettura",
    r_implausible: "Scartata: salto non plausibile",
    r_unreadable: "Non leggibile",
    r_wrong_digits: "Scartata: troppe cifre",
    r_error: "Errore",
    r_corrected: "Impostata a mano",
    never: "mai letto",
    just_now: "ora",
    min_ago: "{n} min fa",
    h_ago: "{n} h fa",
    d_ago: "{n} g fa",
    read: "letto {v}",
    reading_now: "lettura in corso…",
    problem: "Problema",
    paused: "In pausa",
    today: "Oggi",
    yesterday: "Ieri",
    last_24h: "Ultime 24 h",
    per_hour: "all'ora",
    peak: "picco {v}",
    no_data: "ancora nessun dato",
    frame: "Ultimo fotogramma",
    digits_read: "letto {v}",
    to_confirm: "da confermare: {v}",
    confidence: "Affidabilità",
    read_now: "Leggi subito il contatore",
    reading: "Lettura in corso…",
    auto_on: "Lettura automatica: attiva",
    auto_off: "Lettura automatica: disattivata",
    no_entity: "Seleziona il sensore di lettura di un dispositivo Meter Vision.",
    e_entity: "Sensore di lettura",
    e_name: "Titolo",
    e_show_counter: "Mostra totalizzatore",
    e_show_consumption: "Mostra consumi",
    e_show_chart: "Mostra grafico orario",
    e_show_frame: "Mostra ultimo fotogramma",
    e_show_result: "Mostra ultimo esito",
    e_show_buttons: "Mostra pulsanti"
  }
};

function langOf(hass) {
  const l = (hass && ((hass.locale && hass.locale.language) || hass.language)) ||
    (typeof navigator !== "undefined" ? navigator.language : "en");
  return String(l || "en").toLowerCase().split("-")[0];
}

function t(hass, key, vars) {
  const table = STRINGS[langOf(hass)] || STRINGS.en;
  let s = table[key] != null ? table[key] : (STRINGS.en[key] != null ? STRINGS.en[key] : key);
  if (vars) for (const k of Object.keys(vars)) s = s.replace("{" + k + "}", vars[k]);
  return s;
}

/* Decimals of the reading: the decimal wheels plus the pointer dials. */
const precisionOf = (a) => (a.decimal_places || 0) + (a.pointer_dials || 0);

/* Maps the integration's translation keys to the card's internal roles. */
const SIBLINGS = {
  last_result: "result",
  confidence: "confidence",
  last_read: "last",
  value_read: "value_read",
  problem: "problem",
  reading_in_progress: "busy",
  read_now: "button",
  last_frame: "frame",
  automatic_reading: "auto",
  max_increase: "max_increase"
};

const TYPES = {
  water: { icon: "mdi:water", color: "var(--blue-color, #2196f3)" },
  gas: { icon: "mdi:fire", color: "var(--orange-color, #ff9800)" },
  energy: { icon: "mdi:flash", color: "var(--amber-color, #ffc107)" }
};
const RESULTS = {
  accepted: { icon: "mdi:check-circle", color: "var(--success-color, #4caf50)" },
  unconfirmed: { icon: "mdi:timer-sand", color: "var(--warning-color, #ff9800)" },
  decrease: { icon: "mdi:arrow-down-bold-circle", color: "var(--warning-color, #ff9800)" },
  implausible: { icon: "mdi:alert-octagon", color: "var(--error-color, #f44336)" },
  unreadable: { icon: "mdi:eye-off", color: "var(--warning-color, #ff9800)" },
  wrong_digits: { icon: "mdi:numeric-positive-1", color: "var(--warning-color, #ff9800)" },
  error: { icon: "mdi:alert-circle", color: "var(--error-color, #f44336)" },
  corrected: { icon: "mdi:pencil-circle", color: "var(--info-color, #2196f3)" }
};
const DASH = "–";
const MID = "·";
const UNAVAILABLE = ["unavailable", "unknown"];
const HOUR = 36e5;

function findReadingEntity(hass) {
  const reg = (hass && hass.entities) || {};
  for (const id of Object.keys(reg)) {
    const e = reg[id];
    if (e && e.platform === INTEGRATION && e.translation_key === "reading") return id;
  }
  return null;
}

function discoverSiblings(hass, readingEntity) {
  const out = {};
  const reg = (hass && hass.entities) || {};
  const me = reg[readingEntity];
  if (!me || !me.device_id) return out;
  for (const id of Object.keys(reg)) {
    const e = reg[id];
    if (!e || e.device_id !== me.device_id || e.platform !== INTEGRATION) continue;
    const role = SIBLINGS[e.translation_key];
    if (role) out[role] = id;
  }
  return out;
}

async function ensureHaForm() {
  if (customElements.get("ha-form")) return;
  try {
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: "entities", entities: [] });
    if (card && card.constructor && card.constructor.getConfigElement) await card.constructor.getConfigElement();
  } catch (e) {
    /* ha-form will be loaded by the edit dialog */
  }
}

/* Value of a step series at time ts: the last point at or before it. */
function valueAt(pts, ts) {
  let v = null;
  for (const p of pts) {
    if (p[0] > ts) break;
    v = p[1];
  }
  return v === null && pts.length ? pts[0][1] : v;
}

function consumption(pts, from, to) {
  if (!pts.length || pts[pts.length - 1][0] < from) return null;
  const a = valueAt(pts, from), b = valueAt(pts, to);
  return a === null || b === null ? null : Math.max(0, b - a);
}

const DEFAULTS = {
  show_counter: true,
  show_consumption: true,
  show_chart: true,
  show_frame: true,
  show_result: true,
  show_buttons: true
};

const STYLE = `
:host{display:block}
ha-card{padding:12px 16px 14px;box-sizing:border-box;height:100%}
.head{display:flex;align-items:center;gap:12px;cursor:pointer}
.iconwrap{width:40px;height:40px;min-width:40px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.iconwrap ha-icon{--mdc-icon-size:22px}
.iconwrap.pulse{animation:mrpulse 1.6s ease-in-out infinite}
@keyframes mrpulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--mr-color,#2196f3) 35%,transparent)}50%{box-shadow:0 0 0 8px transparent}}
.titles{flex:1;min-width:0}
.name{font-size:14px;font-weight:500;color:var(--primary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub{font-size:12px;color:var(--secondary-text-color);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub b{font-weight:500}
.chips{display:flex;gap:6px}
.chip{font-size:11px;font-weight:500;padding:3px 8px;border-radius:10px;white-space:nowrap}
.chip.bad{background:color-mix(in srgb,var(--error-color,#f44336) 15%,transparent);color:var(--error-color,#f44336)}
.chip.idle{background:var(--secondary-background-color);color:var(--secondary-text-color)}
.counter{margin-top:14px;display:flex;align-items:center;justify-content:center;gap:10px;cursor:pointer}
.wheels{display:flex;gap:3px;padding:5px;border-radius:10px;background:#15181d;box-shadow:inset 0 1px 4px rgba(0,0,0,.6)}
.wheel{width:24px;height:36px;border-radius:4px;display:flex;align-items:center;justify-content:center;font:600 22px/1 "Roboto Mono","SF Mono",Menlo,Consolas,monospace;color:#f5f5f5;background:linear-gradient(#2b3038,#3d434d 45%,#2b3038)}
.wheel.dec{color:#fff;background:linear-gradient(#8e1b1b,#c62828 45%,#8e1b1b)}
.unit{font-size:15px;font-weight:500;color:var(--secondary-text-color)}
.stats{margin-top:14px;display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.stat{padding:8px 10px;border-radius:12px;background:var(--secondary-background-color);min-width:0}
.slabel{font-size:11px;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sval{font-size:16px;font-weight:600;color:var(--primary-text-color);margin-top:2px;white-space:nowrap;font-variant-numeric:tabular-nums}
.sval small{font-size:11px;font-weight:400;color:var(--secondary-text-color);margin-left:2px}
.chart{margin-top:12px;cursor:pointer}
.chartcap{display:flex;justify-content:space-between;font-size:11px;color:var(--secondary-text-color);margin-bottom:4px}
.bars{height:54px}
.bars svg{width:100%;height:100%;display:block}
.frame{position:relative;margin-top:12px;cursor:pointer}
.frame img{display:block;width:100%;max-height:150px;object-fit:cover;border-radius:12px;background:var(--secondary-background-color)}
.frame.expand img{max-height:none;object-fit:contain}
.cap{position:absolute;left:8px;bottom:8px;font-size:11px;font-weight:500;padding:3px 8px;border-radius:10px;color:#fff;background:rgba(0,0,0,.55)}
.result{margin-top:12px;display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;color:var(--primary-text-color)}
.result ha-icon{--mdc-icon-size:18px}
.result .rtxt{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.result .rsub{color:var(--secondary-text-color);font-size:12px}
.foot{margin-top:12px;display:flex;align-items:center;gap:6px}
.conf{display:flex;align-items:center;gap:8px;cursor:pointer;flex:1;min-width:0}
.conflabel{font-size:12px;color:var(--secondary-text-color)}
.dots{display:flex;gap:3px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--divider-color)}
.dot.on{background:var(--primary-color)}
.confval{font-size:12px;color:var(--secondary-text-color);font-variant-numeric:tabular-nums}
.rbtn{border:none;background:none;cursor:pointer;padding:6px;border-radius:50%;color:var(--secondary-text-color);display:flex}
.rbtn:hover{background:var(--secondary-background-color)}
.rbtn ha-icon{--mdc-icon-size:18px;display:block;width:18px;height:18px;line-height:0}
.rbtn.spin ha-icon{animation:mrrot 1s linear infinite;transform-origin:50% 50%}
.rbtn.on{color:var(--primary-color);background:color-mix(in srgb,var(--primary-color) 14%,transparent)}
.rbtn[disabled]{opacity:.4;cursor:default;pointer-events:none}
@keyframes mrrot{to{transform:rotate(360deg)}}
.warn{font-size:12px;color:var(--error-color,#f44336);margin-top:8px}
[hidden]{display:none!important}
`;

class MeterVisionCard extends HTMLElement {
  static getStubConfig(hass) {
    return { entity: findReadingEntity(hass) || "" };
  }

  static async getConfigElement() {
    await ensureHaForm();
    return document.createElement(EDITOR_TAG);
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._cfg = Object.assign({}, DEFAULTS, config, { entity: config.entity || "" });
    this._built = false;
    this._lastSig = null;
    this._hist = null;
    this._histAt = 0;
    if (this._hass) {
      this._build();
      this._refresh();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._cfg) return;
    if (!this._built) this._build();
    this._refresh();
  }

  getCardSize() {
    return this._cfg && this._cfg.show_frame ? 8 : 5;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto", min_columns: 6 };
  }

  _t(key, vars) {
    return t(this._hass, key, vars);
  }

  _ents() {
    return this._cfg.entity ? discoverSiblings(this._hass, this._cfg.entity) : {};
  }

  _more(id) {
    if (id) this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: id }, bubbles: true, composed: true }));
  }

  _st(id) {
    return (this._hass && id && this._hass.states[id]) || null;
  }

  _num(id) {
    const s = this._st(id);
    const v = s ? parseFloat(s.state) : NaN;
    return isNaN(v) ? null : v;
  }

  _fmt(v, decimals) {
    if (v === null || v === undefined || !isFinite(v)) return DASH;
    const locale = (this._hass && this._hass.locale && this._hass.locale.language) || langOf(this._hass);
    try {
      return new Intl.NumberFormat(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(v);
    } catch (e) {
      return v.toFixed(decimals);
    }
  }

  /* Consumption figures: fewer decimals as the number grows (412 L, 12.3 m³, 0.412 m³). */
  _fmtUse(v, decimals) {
    if (v === null || v === undefined) return DASH;
    return this._fmt(v, v >= 100 ? 0 : v >= 10 ? Math.min(decimals, 1) : Math.min(decimals, 3));
  }

  _rel(ts) {
    if (!ts || UNAVAILABLE.includes(ts)) return this._t("never");
    const e = (Date.now() - new Date(ts).getTime()) / 1e3;
    if (!isFinite(e)) return this._t("never");
    if (e < 60) return this._t("just_now");
    if (e < 3600) return this._t("min_ago", { n: Math.floor(e / 60) });
    if (e < 86400) return this._t("h_ago", { n: Math.floor(e / 3600) });
    return this._t("d_ago", { n: Math.floor(e / 86400) });
  }

  _build() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const dots = '<div class="dot"></div>'.repeat(10);
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        <div class="head" id="head">
          <div class="iconwrap" id="iconwrap"><ha-icon id="icon" icon="mdi:counter"></ha-icon></div>
          <div class="titles"><div class="name" id="name"></div><div class="sub" id="sub"></div></div>
          <div class="chips"><div class="chip idle" id="paused" hidden></div><div class="chip bad" id="problem" hidden></div></div>
        </div>
        <div class="counter" id="counter" hidden><div class="wheels" id="wheels"></div><span class="unit" id="unit"></span></div>
        <div class="stats" id="stats" hidden>
          <div class="stat"><div class="slabel" id="l_today"></div><div class="sval" id="v_today">${DASH}</div></div>
          <div class="stat"><div class="slabel" id="l_yesterday"></div><div class="sval" id="v_yesterday">${DASH}</div></div>
          <div class="stat"><div class="slabel" id="l_24h"></div><div class="sval" id="v_24h">${DASH}</div></div>
        </div>
        <div class="chart" id="chart" hidden>
          <div class="chartcap"><span id="chartl"></span><span id="chartr"></span></div>
          <div class="bars" id="bars"></div>
        </div>
        <div class="frame" id="frame" hidden><img id="img" alt="" /><div class="cap" id="cap"></div></div>
        <div class="result" id="result" hidden>
          <ha-icon id="ricon" icon="mdi:check-circle"></ha-icon>
          <span class="rtxt"><span id="rtext"></span> <span class="rsub" id="rsub"></span></span>
        </div>
        <div class="foot" id="foot">
          <div class="conf" id="conf" hidden>
            <span class="conflabel" id="conflabel"></span><div class="dots">${dots}</div>
            <span class="confval" id="confval"></span>
          </div>
          <button class="rbtn" id="autobtn" hidden><ha-icon id="autoicon" icon="mdi:timer-outline"></ha-icon></button>
          <button class="rbtn" id="readbtn" hidden><ha-icon id="readicon" icon="mdi:camera-iris"></ha-icon></button>
        </div>
        <div class="warn" id="warn" hidden></div>
      </ha-card>`;
    const r = this.shadowRoot;
    const on = (id, fn) => r.getElementById(id).addEventListener("click", fn);
    on("head", () => this._more(this._cfg.entity));
    on("counter", () => this._more(this._cfg.entity));
    on("stats", () => this._more(this._cfg.entity));
    on("chart", () => this._more(this._cfg.entity));
    on("result", () => this._more(this._ents().result));
    on("conf", () => this._more(this._ents().confidence));
    const fr = r.getElementById("frame");
    fr.addEventListener("click", () => fr.classList.toggle("expand"));
    r.getElementById("img").addEventListener("error", () => {
      fr.hidden = true;
    });
    on("readbtn", (e) => {
      e.stopPropagation();
      const b = this._ents().button;
      if (this._hass && b) this._hass.callService("button", "press", { entity_id: b });
    });
    on("autobtn", (e) => {
      e.stopPropagation();
      const s = this._ents().auto;
      if (this._hass && s) this._hass.callService("switch", "toggle", { entity_id: s });
    });
    r.getElementById("l_today").textContent = this._t("today");
    r.getElementById("l_yesterday").textContent = this._t("yesterday");
    r.getElementById("l_24h").textContent = this._t("last_24h");
    r.getElementById("chartl").textContent = this._t("per_hour") + " " + MID + " " + this._t("last_24h").toLowerCase();
    r.getElementById("conflabel").textContent = this._t("confidence");
    this._built = true;
  }

  /* History of the reading since the start of yesterday (local time), cached for 5 minutes. */
  _loadHistory() {
    const id = this._cfg.entity, now = Date.now();
    if (this._histFor === id && now - this._histAt < 3e5) return;
    this._histFor = id;
    this._histAt = now;
    const day = new Date();
    day.setHours(0, 0, 0, 0);
    const start = Math.min(day.getTime() - 24 * HOUR, now - 25 * HOUR);
    const t0 = new Date(start).toISOString(), t1 = new Date(now).toISOString();
    this._hass
      .callApi("GET", `history/period/${t0}?filter_entity_id=${id}&end_time=${encodeURIComponent(t1)}&minimal_response&no_attributes`)
      .then((res) => {
        this._hist = ((res && res[0]) || [])
          .map((s) => [+new Date(s.last_changed || s.last_updated), parseFloat(s.state)])
          .filter((p) => isFinite(p[0]) && isFinite(p[1]))
          .sort((a, b) => a[0] - b[0]);
        this._lastSig = null;
        this._refresh();
      })
      .catch(() => {
        this._histAt = 0;
      });
  }

  _updateUsage(value, decimals, unit, color) {
    const c = this._cfg, r = this.shadowRoot;
    const stats = r.getElementById("stats"), chart = r.getElementById("chart");
    stats.hidden = !c.show_consumption;
    chart.hidden = !c.show_chart;
    if (!c.show_consumption && !c.show_chart) return;
    this._loadHistory();
    const now = Date.now();
    const pts = (this._hist || []).slice();
    if (value !== null) pts.push([now, value]);
    const day = new Date();
    day.setHours(0, 0, 0, 0);
    const midnight = day.getTime();
    const show = (id, v) => {
      r.getElementById(id).innerHTML = v === null ? DASH : `${this._fmtUse(v, decimals)}<small>${unit}</small>`;
    };
    show("v_today", consumption(pts, midnight, now));
    show("v_yesterday", consumption(pts, midnight - 24 * HOUR, midnight));
    show("v_24h", consumption(pts, now - 24 * HOUR, now));

    const bars = [];
    const end = Math.ceil(now / HOUR) * HOUR;
    for (let i = 24; i >= 1; i--) {
      const a = end - i * HOUR, b = Math.min(a + HOUR, now);
      bars.push({ at: a, v: pts.length && pts[0][0] <= b ? consumption(pts, a, b) : null });
    }
    const max = Math.max(0, ...bars.map((x) => x.v || 0));
    r.getElementById("chartr").textContent = max > 0 ? this._t("peak", { v: this._fmtUse(max, decimals) + " " + unit }) :
      (pts.length < 2 ? this._t("no_data") : "");
    const w = 100 / 24;
    const rects = bars.map((x, i) => {
      const h = max > 0 && x.v ? Math.max(1.5, (x.v / max) * 52) : 0;
      const hour = new Date(x.at).toLocaleTimeString(langOf(this._hass), { hour: "2-digit", minute: "2-digit" });
      const tip = `${hour} ${MID} ${x.v === null ? DASH : this._fmtUse(x.v, decimals) + " " + unit}`;
      return `<rect x="${(i * w + w * 0.15).toFixed(2)}" y="${(54 - Math.max(h, 1)).toFixed(2)}" width="${(w * 0.7).toFixed(2)}" height="${Math.max(h, 1).toFixed(2)}" rx="1" fill="${h ? color : "var(--divider-color)"}"><title>${tip}</title></rect>`;
    });
    r.getElementById("bars").innerHTML = `<svg viewBox="0 0 100 54" preserveAspectRatio="none">${rects.join("")}</svg>`;
  }

  _updateCounter(value, a, unit) {
    const r = this.shadowRoot, wrap = r.getElementById("counter");
    wrap.hidden = !this._cfg.show_counter;
    if (wrap.hidden) return;
    const decimals = a.decimal_places || 0;
    let text = value === null ? "" : Math.floor(value * Math.pow(10, decimals) + 1e-6).toString();
    const width = Math.max(a.digits || 0, text.length || 6, decimals + 1);
    text = value === null ? DASH.repeat(width) : text.padStart(width, "0");
    r.getElementById("wheels").innerHTML = [...text]
      .map((d, i) => `<span class="wheel${i >= text.length - decimals ? " dec" : ""}">${d === DASH ? "&nbsp;" : d}</span>`)
      .join("");
    r.getElementById("unit").textContent = unit;
  }

  _refresh() {
    if (!this._built || !this._hass) return;
    const c = this._cfg, r = this.shadowRoot;
    const warn = r.getElementById("warn");
    const st = this._st(c.entity);
    if (!st) {
      warn.hidden = false;
      warn.textContent = this._t("no_entity");
      return;
    }
    warn.hidden = true;
    const e = this._ents();
    const a = st.attributes || {};
    const type = TYPES[a.meter_type] || TYPES.water;
    const unit = a.unit_of_measurement || "";
    const value = UNAVAILABLE.includes(st.state) ? null : this._num(c.entity);
    const resultState = (this._st(e.result) || {}).state;
    const result = RESULTS[resultState] ? resultState : null;
    const busy = (this._st(e.busy) || {}).state === "on";
    const problem = (this._st(e.problem) || {}).state === "on";
    const auto = this._st(e.auto);
    const last = (this._st(e.last) || {}).state;
    const conf = this._num(e.confidence);
    const frame = this._st(e.frame);
    const ra = (this._st(e.result) || {}).attributes || {};
    const sig = [st.state, a.pending_value, resultState, busy, problem, auto && auto.state, last, conf,
      frame && frame.state, frame && frame.attributes.entity_picture, ra.digits_read, langOf(this._hass), c.name,
      Math.floor(Date.now() / 6e4), this._hist && this._hist.length].join("|");
    if (sig === this._lastSig) return;
    this._lastSig = sig;

    const device = this._hass.devices && this._hass.entities && this._hass.entities[c.entity] &&
      this._hass.devices[this._hass.entities[c.entity].device_id];
    r.getElementById("name").textContent = c.name || (device && (device.name_by_user || device.name)) || this._t("default_title");
    const iw = r.getElementById("iconwrap");
    iw.style.background = `color-mix(in srgb, ${type.color} 18%, transparent)`;
    iw.style.setProperty("--mr-color", type.color);
    iw.classList.toggle("pulse", busy);
    const ic = r.getElementById("icon");
    ic.setAttribute("icon", type.icon);
    ic.style.color = type.color;

    const parts = [];
    if (value !== null) parts.push(`<b>${this._fmt(value, precisionOf(a))} ${unit}</b>`);
    parts.push(busy ? this._t("reading_now") : this._t("read", { v: this._rel(last) }));
    r.getElementById("sub").innerHTML = parts.join(" " + MID + " ");
    const pc = r.getElementById("problem");
    pc.hidden = !problem;
    pc.textContent = this._t("problem");
    const pa = r.getElementById("paused");
    pa.hidden = !(auto && auto.state === "off");
    pa.textContent = this._t("paused");

    this._updateCounter(value, a, unit);
    this._updateUsage(value, precisionOf(a), unit, type.color);

    const fr = r.getElementById("frame"), img = r.getElementById("img");
    const pic = frame && frame.attributes.entity_picture;
    fr.hidden = !(c.show_frame && pic && !UNAVAILABLE.includes(frame.state));
    if (!fr.hidden && img.getAttribute("src") !== pic) img.src = pic;
    const capParts = [this._t("frame")];
    if (frame && !UNAVAILABLE.includes(frame.state)) capParts.push(this._rel(frame.state));
    if (ra.digits_read) capParts.push(this._t("digits_read", { v: ra.digits_read }));
    r.getElementById("cap").textContent = capParts.join(" " + MID + " ");

    const rr = r.getElementById("result");
    rr.hidden = !(c.show_result && result);
    if (result) {
      const R = RESULTS[result];
      const ri = r.getElementById("ricon");
      ri.setAttribute("icon", R.icon);
      ri.style.color = R.color;
      r.getElementById("rtext").textContent = this._t("r_" + result);
      let sub = "";
      if (a.pending_value !== null && a.pending_value !== undefined) {
        sub = this._t("to_confirm", { v: this._fmt(a.pending_value, precisionOf(a)) + " " + unit });
      } else if (result !== "accepted" && result !== "corrected" && ra.digits_read) {
        sub = this._t("digits_read", { v: ra.digits_read });
      }
      r.getElementById("rsub").textContent = sub;
    }

    r.getElementById("conf").hidden = !(c.show_result && e.confidence);
    const c10 = conf === null ? null : Math.max(0, Math.min(10, Math.round(conf)));
    r.getElementById("confval").textContent = c10 === null ? DASH : c10 + "/10";
    r.querySelectorAll(".dot").forEach((d, i) => d.classList.toggle("on", c10 !== null && i < c10));

    const ab = r.getElementById("autobtn");
    ab.hidden = !(c.show_buttons && auto);
    if (auto) {
      const isOn = auto.state === "on";
      ab.classList.toggle("on", isOn);
      ab.title = this._t(isOn ? "auto_on" : "auto_off");
      r.getElementById("autoicon").setAttribute("icon", isOn ? "mdi:timer-outline" : "mdi:timer-off-outline");
    }
    const rb = r.getElementById("readbtn"), btn = this._st(e.button);
    rb.hidden = !(c.show_buttons && btn);
    if (btn) {
      rb.toggleAttribute("disabled", btn.state === "unavailable" || busy);
      rb.classList.toggle("spin", busy);
      r.getElementById("readicon").setAttribute("icon", busy ? "mdi:loading" : "mdi:camera-iris");
      rb.title = this._t(busy ? "reading" : "read_now");
    }
  }
}

class MeterVisionCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({}, config);
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  connectedCallback() {
    this._render();
  }

  _schema() {
    const flag = (name) => ({ name, selector: { boolean: {} } });
    return [
      { name: "entity", required: true, selector: { entity: { integration: INTEGRATION, domain: "sensor" } } },
      { name: "name", selector: { text: {} } },
      {
        type: "grid",
        name: "",
        schema: ["show_counter", "show_consumption", "show_chart", "show_frame", "show_result", "show_buttons"].map(flag)
      }
    ];
  }

  async _render() {
    if (!this._config || !this._hass) return;
    await ensureHaForm();
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = Object.assign({}, this._config, ev.detail.value);
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = Object.assign({}, DEFAULTS, this._config);
    this._form.schema = this._schema();
    this._form.computeLabel = (s) => t(this._hass, "e_" + s.name);
  }
}

if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, MeterVisionCardEditor);
if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, MeterVisionCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TAG,
    name: t(null, "card_name"),
    description: t(null, "card_description"),
    preview: true,
    documentationURL: "https://github.com/leinemann/ha-meter-vision"
  });
  console.info(`%c METER-VISION-CARD %c ${CARD_VERSION} `, "color:#fff;background:#0277bd;font-weight:700", "color:#0277bd;background:#fff");
}
