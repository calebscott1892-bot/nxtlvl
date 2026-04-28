import { C4_WORDMARK_MORPH_PAIRS } from './c4WordmarkData.js';

const FULL_VIEWBOX = '50 100 880 400';
const FULL_ASPECT = 880 / 400;
const LOCKUP_TRANSFORM = 'translate(18 -273) scale(1.5)';

const FULL_UPRIGHT = {
  fourBody: '303.88 303.92 303.87 401.82 271.12 401.82 271.12 343.47 228.18 405.86 271.12 405.86 255.72 428.97 184.95 428.97 184.95 413.1 263.67 303.92 303.88 303.92',
  fourArm: '344.11 405.86 328.71 428.97 303.88 428.97 303.88 482.39 279.58 482.39 279.58 428.97 264.76 428.97 280.17 405.86 344.11 405.86',
  cArc: 'M227.07,440.52l21.95.11c-17.85,20.3-41.9,34.05-68.37,39.1-42.51,8.81-85.9-10.45-108.08-47.97-18.17-30.46-14.55-69.27,8.95-95.79,15.71-18.02,37.74-29.24,61.48-31.32,26.14-3.66,52.76-1.51,77.99,6.28l-17.77,24.76c-14.77-3.1-29.94-3.81-44.94-2.11-20.89,1.13-40,12.19-51.48,29.78-6.66,13.21-8.03,28.49-3.84,42.69,6.27,22.39,23.69,39.88,45.96,46.15,26.61,5.37,54.24,1.23,78.14-11.68Z',
};

const COLOURS = {
  dark: {
    dormant: { fourBody: '#606264', fourArm: '#707274', cArc: '#d0cecc' },
    mono: { fourBody: '#9a9b9c', fourArm: '#8a8b8c', cArc: '#d0cecc', text: '#e8e6e3' },
  },
  light: {
    dormant: { fourBody: '#b8b9ba', fourArm: '#c5c6c7', cArc: '#e6e4e2' },
    mono: { fourBody: '#414243', fourArm: '#6c6d6d', cArc: '#e6e4e2', text: '#1a1a1b' },
  },
  colour: { fourBody: '#a30000', fourArm: '#22632f', cArc: '#f3f2f3' },
};

function parseCssRgb(value) {
  if (!value || value === 'transparent') return null;
  const match = value.match(/rgba?\(([^)]+)\)/i);
  if (!match) return null;

  const [r, g, b, a = '1'] = match[1]
    .split(',')
    .map((part) => Number.parseFloat(part.trim()));

  if (![r, g, b].every(Number.isFinite) || !Number.isFinite(a) || a === 0) {
    return null;
  }

  return { r, g, b };
}

function isDarkBackground(element) {
  let node = element?.parentElement || document.body;
  while (node && node !== document.documentElement) {
    const rgb = parseCssRgb(window.getComputedStyle(node).backgroundColor);
    if (rgb) {
      const luminance = (0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b) / 255;
      return luminance < 0.45;
    }
    node = node.parentElement;
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function makeSvgNode(tagName, attrs = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tagName);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function renderC4FooterCredit(host) {
  if (!host || host.dataset.c4Mounted === 'true') return;
  host.dataset.c4Mounted = 'true';

  const label = host.dataset.label || 'Designed by C4 Studios';
  const href = host.dataset.href || 'https://c4studios.com.au';
  const size = Number.parseFloat(host.dataset.size || '28');
  const showText = host.dataset.showText === 'true';
  const colorScheme = host.dataset.colorScheme || 'auto';
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const palette = colorScheme === 'dark'
    ? COLOURS.dark
    : colorScheme === 'light'
      ? COLOURS.light
      : isDarkBackground(host)
        ? COLOURS.dark
        : COLOURS.light;
  const width = Math.round(size * FULL_ASPECT);

  const link = document.createElement('a');
  link.className = 'c4-footer-credit';
  link.href = href;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.setAttribute('aria-label', label);

  const svg = makeSvgNode('svg', {
    viewBox: FULL_VIEWBOX,
    width,
    height: size,
    role: 'img',
    'aria-hidden': 'true',
    focusable: 'false',
  });

  const rootGroup = makeSvgNode('g', { transform: LOCKUP_TRANSFORM });
  const cBase = makeSvgNode('path', { d: FULL_UPRIGHT.cArc, fill: palette.mono.cArc });
  const cColour = makeSvgNode('path', { d: FULL_UPRIGHT.cArc, fill: COLOURS.colour.cArc, opacity: '0' });
  const body = makeSvgNode('polygon', { points: FULL_UPRIGHT.fourBody, fill: palette.dormant.fourBody });
  const arm = makeSvgNode('polygon', { points: FULL_UPRIGHT.fourArm, fill: palette.dormant.fourArm });
  const wordGroup = makeSvgNode('g', { opacity: '0' });

  C4_WORDMARK_MORPH_PAIRS.forEach((pair) => {
    const path = makeSvgNode('path', {
      d: pair.normalized.normalizedPaths?.uprightPath || pair.raw.uprightPath,
      fill: palette.mono.text,
    });
    wordGroup.appendChild(path);
  });

  rootGroup.append(cBase, cColour, body, arm, wordGroup);
  svg.appendChild(rootGroup);
  link.appendChild(svg);

  if (showText) {
    const span = document.createElement('span');
    span.className = 'c4-footer-credit__text';
    span.textContent = label;
    link.appendChild(span);
  }

  host.replaceChildren(link);

  if (prefersReducedMotion || !window.gsap) {
    gsapSetStatic(cBase, cColour, body, arm, wordGroup, palette);
    return;
  }

  const timeline = window.gsap.timeline({ paused: true, defaults: { ease: 'power2.out' } });
  timeline
    .to([body, arm], { fill: (index) => index === 0 ? palette.mono.fourBody : palette.mono.fourArm, duration: 0.22 }, 0)
    .to(wordGroup, { opacity: 1, duration: 0.28 }, 0.05)
    .to(cBase, { opacity: 0, duration: 0.2 }, 0.32)
    .to(cColour, { opacity: 1, duration: 0.24 }, 0.34)
    .to(body, { fill: COLOURS.colour.fourBody, duration: 0.22 }, 0.42)
    .to(arm, { fill: COLOURS.colour.fourArm, duration: 0.22 }, 0.5)
    .to(wordGroup.querySelectorAll('path'), {
      y: -3,
      stagger: 0.025,
      yoyo: true,
      repeat: 1,
      duration: 0.16,
      ease: 'power1.inOut',
    }, 0.54);

  let stage = 0;
  const advance = () => {
    if (stage === 0) {
      timeline.tweenTo(0.32);
      stage = 1;
      return;
    }
    if (stage === 1) {
      timeline.play();
      stage = 2;
      return;
    }
    timeline.reverse();
    stage = 0;
  };

  link.addEventListener('mouseenter', advance);
  link.addEventListener('focus', advance);
}

function gsapSetStatic(cBase, cColour, body, arm, wordGroup, palette) {
  cBase.setAttribute('opacity', '1');
  cColour.setAttribute('opacity', '0');
  body.setAttribute('fill', palette.dormant.fourBody);
  arm.setAttribute('fill', palette.dormant.fourArm);
  wordGroup.setAttribute('opacity', '0');
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-c4-footer-credit]').forEach(renderC4FooterCredit);
});
