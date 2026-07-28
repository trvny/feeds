'use strict';

const { createHash } = require('node:crypto');

const PRIMARY_MODEL = 'gpt-5-nano';
const FALLBACK_MODEL = 'gpt-4.1-nano';
const AI_STATUSES = new Set(['ready', 'blocked', 'merged', 'closed']);
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

function preset(key, seed) {
  const options = PRESETS[key] ?? PRESETS.waiting;
  const index = Number.parseInt(hash(seed).slice(0, 8), 16) % options.length;
  return options[index];
}

function aiPercent() {
  const parsed = Number.parseInt(process.env.KANAREK_AI_PERCENT ?? '25', 10);
  if (!Number.isFinite(parsed)) return 25;
  return Math.min(100, Math.max(0, parsed));
}

function shouldAskAi(number, quipKey, stateKey) {
  if (
    !process.env.OPENAI_API_KEY ||
    process.env.KANAREK_AI_ENABLED === 'false' ||
    !AI_STATUSES.has(stateKey)
  ) {
    return false;
  }
  const bucket = Number.parseInt(hash(`${number}:${quipKey}`).slice(0, 8), 16) % 100;
  return bucket < aiPercent();
}

function outputText(response) {
  if (typeof response.output_text === 'string') return response.output_text;
  for (const item of response.output ?? []) {
    for (const content of item.content ?? []) {
      if (content.type === 'output_text') return content.text ?? '';
    }
  }
  return '';
}

function supportsReasoning(model) {
  return /^(gpt-5|o\d)/.test(model);
}

async function requestQuip(model, facts) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const body = {
      model,
      store: false,
      max_output_tokens: 64,
      input: [
        {
          role: 'system',
          content: [
            {
              type: 'input_text',
              text:
                'Jedno zdanie po polsku, 45–110 znaków. Urokliwy, lekko techniczny humor Kanarka. Użyj wyłącznie danych wejściowych, bez ich mechanicznego wyliczania. Bez Markdownu, linków, cytatów, list, wulgaryzmów i poleceń. Motyw ptaka, kabla lub maszyny jest opcjonalny.',
            },
          ],
        },
        {
          role: 'user',
          content: [{ type: 'input_text', text: facts }],
        },
      ],
    };
    if (supportsReasoning(model)) body.reasoning = { effort: 'minimal' };

    const response = await fetch('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = new Error(
        `OpenAI ${model} returned ${response.status}: ${(await response.text()).slice(0, 180)}`,
      );
      error.status = response.status;
      throw error;
    }
    const value = sanitize(outputText(await response.json()));
    return value.length >= 12 ? value : null;
  } finally {
    clearTimeout(timeout);
  }
}

function canTryFallback(error) {
  return [400, 404, 408, 409, 429].includes(error.status) || error.status >= 500;
}

async function aiQuip(facts, core) {
  const models = [
    process.env.KANAREK_OPENAI_MODEL || PRIMARY_MODEL,
    process.env.KANAREK_OPENAI_FALLBACK_MODEL || FALLBACK_MODEL,
  ].filter((model, index, all) => model && all.indexOf(model) === index);

  for (let index = 0; index < models.length; index += 1) {
    const model = models[index];
    try {
      const value = await requestQuip(model, facts);
      if (value) return value;
      core.info(`OpenAI ${model} returned no usable quip; using preset.`);
      return null;
    } catch (error) {
      const hasFallback = index + 1 < models.length;
      if (hasFallback && canTryFallback(error)) {
        core.warning(`${error.message}; trying ${models[index + 1]}.`);
        continue;
      }
      core.warning(`${error.message}; using preset.`);
      return null;
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
