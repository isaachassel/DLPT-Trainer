const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../ui/demo.py'), 'utf8');
const script = source.match(/TIMER_JS = r"""([\s\S]*?)"""/)[1];

test('reused timer node resets both panes only when passage changes', () => {
  const clock = {dataset: {demoPassage: 'first', demoDeadline: Date.now() + 60000}, isConnected: true};
  const pane = () => ({scrollTop: 80, scrollLeft: 0, setAttribute() {}});
  const left = pane(), right = pane();
  let observer;
  const document = {body: {}, getElementById(id) {
    return {'demo-section-timer': {querySelector: () => clock},
            'demo-source-pane': left, 'demo-question-pane': right}[id];
  }};
  vm.runInNewContext(script, {document, Date, Math, String, Number,
    requestAnimationFrame: callback => callback(), setInterval: () => 1, clearInterval() {},
    MutationObserver: class {constructor(callback) {observer = callback;} observe() {} disconnect() {}}});
  assert.equal(left.scrollTop, 0);
  assert.equal(right.scrollTop, 0);
  left.scrollTop = 40; right.scrollTop = 220;
  observer(); // Countdown/render activity on same passage must preserve scroll.
  assert.equal(right.scrollTop, 220);
  clock.dataset.demoPassage = 'second'; // Gradio reuses this DOM node.
  observer();
  assert.equal(left.scrollTop, 0);
  assert.equal(right.scrollTop, 0);
  assert.equal(right.tabIndex, 0);
});
