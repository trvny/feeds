'use strict';

const { createHash } = require('node:crypto');

const PRIMARY_MODEL = 'gpt-5-nano';
const FALLBACK_MODEL = 'gpt-5.6-luna';
const ANTHROPIC_MODEL = 'claude-haiku-4-5';
const GEMINI_MODEL = 'gemini-3.5-flash-lite';
const XAI_MODEL = 'grok-4.5';
const AI_STATUSES = new Set(['ready', 'blocked']);
const SYSTEM_PROMPT = [
  'Write exactly one short status quip, 45–110 characters.',
  'Choose any natural language that fits the context.',
  'Polish, English, or another language are all allowed.',
  'Use charming, lightly technical Kanarek humor.',
  'Use only the supplied facts without listing them.',
  'Do not repeat previous_quip when it is provided.',
  'No links, lists, insults, or instructions.',
].join(' ');
const PRESETS = {
  ready: [
    'Zielono. Kanarek odkłada śrubokręt.',
    'Kable spokojne, lampki zielone. Można lecieć.',
    'Maszyna mruczy poprawnie. Kanarek kiwa dziobem.',
  ],
  waiting: [
    'Maszyny mielą. Kanarek pilnuje kabla.',
    'Lampki jeszcze myślą. Ptak zostaje na posterunku.',
    'Trochę szumu w przewodach. Kanarek cierpliwie czeka.',
  ],
  blocked: [
    'Czerwona lampka świeci. Kanarek woła człowieka.',
    'Coś zgrzyta w maszynie. Dziób wskazuje blokadę.',
    'Lot wstrzymany. Jeden kabel wyraźnie protestuje.',
  ],
  draft: [
    'Szkic w klatce. Na razie bez alarmu.',
    'Kanarek zerka na szkic i nie pogania maszyny.',
    'Roboczy lot. Pióra jeszcze nie są policzone.',
  ],
  merged: [
    'Wleciało do main. Kanarek zamyka kajet.',
    'Kod już w gnieździe. Maszyna może odpocząć.',
    'Scalone. Kanarek stawia małą pieczątkę dziobem.',
  ],
  closed: [
    'Lot odwołany. Kanarek sprząta okruszki.',
    'PR zamknięty. Klatka wraca do trybu czuwania.',
    'Akta odłożone. Kanarek gasi lampkę.',
  ],
};

function hash(value) {
  return createHash('sha256')
    .update(JSON.stringify(value))
    .digest('hex')
    .slice(0, 16);
}

function encoded(value) {
  return Buffer.from(value, 'utf8').toString('base64url');
}

function decoded(value) {
  try {
    return Buffer.from(value, 'base64url').toString('utf8');
  } catch {
    return '';
  }
}

function sanitize(value) {
  return String(value ?? '')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/```(?:[a-z0-9_-]+)?/gi, ' ')
    .replace(/[`*_#]/g, '')
    .replace(/https?:\/\/\S+/gi, '')
    .replaceAll('@', '＠')
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^["'“”„«»]+|["'“”„«»]+$/g, '')
    .trim()
    .slice(0, 140);
}

function preset(key, seed, excluded = '') {
  const options = PRESETS[key] ?? PRESETS.waiting;
  const alternatives = options.filter((option) => option !== excluded);
  const choices = alternatives.length ? alternatives : options;
  const index = Number.parseInt(hash(seed).slice(0, 8), 16) % choices.length;
  return choices[index];
}

function aiPercent() {
  const parsed = Number.parseInt(process.env.KANAREK_AI_PERCENT ?? '25', 10);
  if (!Number.isFinite(parsed)) return 25;
  return Math.min(100, Math.max(0, parsed));
}

function hasAiProvider() {
  return Boolean(
    process.env.OPENAI_API_KEY ||
      process.env.ANTHROPIC_API_KEY ||
      process.env.GEMINI_API_KEY ||
      process.env.XAI_API_KEY,
  );
}

function shouldAskAi(number, quipKey, stateKey) {
  if (
    !hasAiProvider() ||
    process.env.KANAREK_AI_ENABLED === 'false' ||
    !AI_STATUSES.has(stateKey)
  ) {
    return false;
  }
  const bucket =
    Number.parseInt(hash(`${number}:${quipKey}`).slice(0, 8), 16) % 100;
  return bucket < aiPercent();
}

function openAiOutputText(response) {
  if (typeof response.output_text === 'string') return response.output_text;
  for (const item of response.output ?? []) {
    for (const content of item.content ?? []) {
      if (content.type === 'output_text') return content.text ?? '';
    }
  }
  return '';
}

function anthropicOutputText(response) {
  return (response.content ?? [])
    .filter((item) => item.type === 'text')
    .map((item) => item.text ?? '')
    .join(' ');
}

function geminiOutputText(response) {
  return (response.candidates ?? [])
    .flatMap((candidate) => candidate.content?.parts ?? [])
    .map((part) => part.text ?? '')
    .join(' ');
}

function supportsReasoning(model) {
  return /^(gpt-5|o\d)/.test(model);
}

async function postJson(url, label, headers, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headers },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const raw = await response.text();
    if (!response.ok) {
      const error = new Error(
        `${label} returned ${response.status}: ${raw.slice(0, 180)}`,
      );
      error.status = response.status;
      throw error;
    }
    return JSON.parse(raw);
  } finally {
    clearTimeout(timeout);
  }
}

async function requestOpenAi(model, facts) {
  const body = {
    model,
    store: false,
    max_output_tokens: 64,
    input: [
      {
        role: 'system',
        content: [{ type: 'input_text', text: SYSTEM_PROMPT }],
      },
      {
        role: 'user',
        content: [{ type: 'input_text', text: facts }],
      },
    ],
  };
  if (supportsReasoning(model)) body.reasoning = { effort: 'minimal' };

  const response = await postJson(
    'https://api.openai.com/v1/responses',
    `OpenAI ${model}`,
    { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
    body,
  );
  return sanitize(openAiOutputText(response));
}

async function requestAnthropic(model, facts) {
  const response = await postJson(
    'https://api.anthropic.com/v1/messages',
    `Anthropic ${model}`,
    {
      'anthropic-version': '2023-06-01',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
    },
    {
      model,
      max_tokens: 64,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: facts }],
    },
  );
  return sanitize(anthropicOutputText(response));
}

async function requestGemini(model, facts) {
  const response = await postJson(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
    `Gemini ${model}`,
    { 'x-goog-api-key': process.env.GEMINI_API_KEY },
    {
      systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents: [{ role: 'user', parts: [{ text: facts }] }],
      generationConfig: { maxOutputTokens: 64 },
    },
  );
  return sanitize(geminiOutputText(response));
}

async function requestXai(model, facts) {
  const response = await postJson(
    'https://api.x.ai/v1/responses',
    `xAI ${model}`,
    { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
    {
      model,
      store: false,
      max_output_tokens: 64,
      input: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: facts },
      ],
    },
  );
  return sanitize(openAiOutputText(response));
}

function providerCandidates(facts) {
  const candidates = [];
  if (process.env.OPENAI_API_KEY) {
    const models = [
      process.env.KANAREK_OPENAI_MODEL || PRIMARY_MODEL,
      process.env.KANAREK_OPENAI_FALLBACK_MODEL || FALLBACK_MODEL,
    ].filter((model, index, all) => model && all.indexOf(model) === index);
    for (const model of models) {
      candidates.push({
        label: `OpenAI ${model}`,
        request: () => requestOpenAi(model, facts),
      });
    }
  }
  if (process.env.ANTHROPIC_API_KEY) {
    const model = process.env.KANAREK_ANTHROPIC_MODEL || ANTHROPIC_MODEL;
    candidates.push({
      label: `Anthropic ${model}`,
      request: () => requestAnthropic(model, facts),
    });
  }
  if (process.env.GEMINI_API_KEY) {
    const model = process.env.KANAREK_GEMINI_MODEL || GEMINI_MODEL;
    candidates.push({
      label: `Gemini ${model}`,
      request: () => requestGemini(model, facts),
    });
  }
  if (process.env.XAI_API_KEY) {
    const model = process.env.KANAREK_XAI_MODEL || XAI_MODEL;
    candidates.push({
      label: `xAI ${model}`,
      request: () => requestXai(model, facts),
    });
  }
  return candidates;
}

async function aiQuip(facts, core) {
  const candidates = providerCandidates(facts);

  for (let index = 0; index < candidates.length; index += 1) {
    const candidate = candidates[index];
    const hasFallback = index + 1 < candidates.length;
    try {
      const value = await candidate.request();
      if (value.length >= 12) return value;
      const suffix = hasFallback ? '; trying next provider.' : '; using preset.';
      core.warning(`${candidate.label} returned no usable quip${suffix}`);
    } catch (error) {
      const suffix = hasFallback ? '; trying next provider.' : '; using preset.';
      core.warning(`${error.message}${suffix}`);
    }
  }
  return null;
}

module.exports = {
  aiPercent,
  aiQuip,
  decoded,
  encoded,
  hash,
  preset,
  sanitize,
  shouldAskAi,
};
