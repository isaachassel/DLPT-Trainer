// Run the actual browser controller against replacement hosts, as Gradio does.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../ui/demo_audio.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

class Audio extends EventTarget {
  constructor(passage) {
    super(); this.dataset = {session:'session', passage}; this.isConnected = true;
    this.plays = 0; this.ended = false;
  }
  async play() { this.plays++; this.ended = false; this.dispatchEvent(new Event('playing')); }
  pause() { this.dispatchEvent(new Event('pause')); }
  removeAttribute() {}
  end() { this.ended = true; this.dispatchEvent(new Event('ended')); }
}
class Button extends EventTarget {
  click() { this.dispatchEvent(new Event('click')); }
}
function host(passage) {
  const audio = new Audio(passage), button = new Button(), status = {};
  return {audio, button, status, querySelector: s => s.startsWith('audio') ? audio : s.includes('play') ? button : status};
}

test('every replacement passage gets two listens and current-passage events', async () => {
  const initial = host('first');
  let current = initial;
  const events = [], observers = [], input = {value:''};
  const bridge = {click: () => events.push(input.value), querySelector() { return this; }};
  const document = {
    body: {},
    getElementById: id => id === 'demo-audio-player' ? current : bridge,
    querySelector: () => input,
  };
  class MutationObserver {
    constructor(fn) { this.fn=fn; observers.push(this); }
    observe(target) { this.target=target; }
    disconnect() { this.target=null; }
  }
  class AudioContext {
    constructor() { this.state='running'; this.currentTime=0; }
    async resume() {}
    async close() {}
    createGain() { return {connect(){},disconnect(){},gain:{setValueAtTime(){},linearRampToValueAtTime(){}}}; }
    createOscillator() { return {frequency:{},connect(){},disconnect(){},start(){},stop(){queueMicrotask(() => this.onended?.());}}; }
  }
  vm.runInNewContext(script, {element:initial, document, MutationObserver, AbortController, AudioContext,
    setTimeout: fn => {queueMicrotask(fn); return 1;}, clearTimeout(){}});
  for (const name of ['first', 'second', 'third']) {
    if (name !== 'first') {
      const old = current;
      old.audio.isConnected=false;
      current=host(name);
      for (const observer of observers) if (observer.target === document.body) observer.fn();
      old.button.click(); // Detached button must not restart the old recording.
      assert.equal(old.audio.plays, 2);
    }
    current.button.click(); await flush();
    assert.equal(current.audio.plays, 1, `${name}: Play button must bind after replacement`);
    current.audio.end(); await flush();
    assert.equal(current.audio.plays, 2);
    current.audio.end(); await flush();
    current.button.click(); await flush();
    assert.equal(current.audio.plays, 2, 'No third play');
    assert.deepEqual(events.slice(-4), ['start1','end1','start2','end2'].map(p => `session|${name}|${p}`));
  }
});
