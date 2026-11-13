// Drive the real local playground through Chrome DevTools and save three demo screenshots.
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const targets = await fetch('http://127.0.0.1:9222/json').then(response => response.json());
const target = targets.find(item => item.type === 'page' && item.url.includes('5173'));
if (!target) throw new Error('local playground tab not found');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolveOpen, reject) => { socket.onopen = resolveOpen; socket.onerror = reject; });
let serial = 0;
const pending = new Map();
socket.onmessage = event => {
  const data = JSON.parse(event.data);
  if (!data.id) return;
  const item = pending.get(data.id);
  if (!item) return;
  pending.delete(data.id);
  data.error ? item.reject(new Error(JSON.stringify(data.error))) : item.resolve(data.result);
};
function command(method, params = {}) {
  const id = ++serial;
  return new Promise((resolveCommand, reject) => {
    pending.set(id, { resolve: resolveCommand, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}
async function waitFor(expression, label) {
  for (let attempt = 0; attempt < 100; attempt++) {
    const value = await evaluate(expression);
    if (value) return value;
    await new Promise(resolveWait => setTimeout(resolveWait, 100));
  }
  throw new Error(`timed out: ${label}`);
}
async function selectScenario(id) {
  await evaluate(`(() => { window.confirm = () => true; const node = document.querySelector('#scenario-select'); const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; setter.call(node, ${JSON.stringify(id)}); node.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
  await waitFor(`document.querySelector('.workspace-meta')?.textContent.includes(${JSON.stringify(id)}) && !document.querySelector('#scenario-select').disabled`, `scenario ${id}`);
}
async function send(text, number) {
  await evaluate(`(() => { const node = document.querySelector('#caller-text'); const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set; setter.call(node, ${JSON.stringify(text)}); node.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
  await waitFor(`!document.querySelector('.primary-button').disabled`, 'send enabled');
  await evaluate(`document.querySelector('.primary-button').click()`);
  await waitFor(`document.querySelectorAll('.message.sophie').length === ${number} && !document.querySelector('.primary-button').textContent.includes('Sending')`, `turn ${number}`);
}
async function tab(label) {
  await evaluate(`(() => { if (!document.querySelector('[role="tab"]')) document.querySelector('.details-toggle').click(); Array.from(document.querySelectorAll('[role="tab"]')).find(node => node.textContent.includes(${JSON.stringify(label)})).click(); return true; })()`);
}
async function screenshot(name) {
  const directory = resolve('docs/assets');
  mkdirSync(directory, { recursive: true });
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  writeFileSync(resolve(directory, name), Buffer.from(result.data, 'base64'));
}

try {
  await waitFor(`document.querySelector('#scenario-select') && !document.querySelector('#scenario-select').disabled`, 'initial page');
  await selectScenario('S01');
  const s01 = ['Hi, how much does your community cost?', 'Do you take Medicaid?', 'Could I tour next Sunday at 3pm?', 'How about next Tuesday at 2pm?', 'What about 3pm that afternoon?', 'My name is James Carter, email james.carter@example.test.', 'Yes.', 'Yes.'];
  for (let i = 0; i < s01.length; i++) await send(s01[i], i + 1);
  await tab('Business state');
  await waitFor(`document.querySelector('.inspector-content')?.textContent.includes('booked') && document.querySelector('.inspector-content')?.textContent.includes('2026-11-17')`, 'S01 booked state');
  await screenshot('m8-s01-booked.png');

  await selectScenario('S03');
  const s03 = ['Book a tour next Wednesday at 10am.', 'My name is Jamie Demo, email jamie.demo@example.test.', 'Yes.', 'Yes.'];
  for (let i = 0; i < s03.length; i++) await send(s03[i], i + 1);
  await tab('Events');
  await waitFor(`document.querySelector('.inspector-content')?.textContent.includes('slot taken')`, 'S03 lost slot event');
  await tab('Business state');
  await waitFor(`document.querySelector('.inspector-content')?.textContent.includes('Tours') && document.querySelector('.inspector-content')?.textContent.includes('No records')`, 'S03 empty tour state');
  await screenshot('m8-s03-lost-slot.png');

  await selectScenario('S02');
  const s02 = ['Move my tour to Thursday at 11am.', 'Yes.', 'Cancel my tour.', 'Yes.'];
  for (let i = 0; i < s02.length; i++) await send(s02[i], i + 1);
  await tab('Business state');
  await waitFor(`document.querySelector('.inspector-content')?.textContent.includes('canceled')`, 'S02 canceled state');
  await screenshot('m8-s02-canceled.png');
  console.log('Captured real UI scenes: S01 booked, S03 lost slot, S02 canceled');
} finally {
  socket.close();
}
