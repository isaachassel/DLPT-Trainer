const bind = () => {
  const audio = element.querySelector('audio[data-demo-audio]');
  const button = element.querySelector('[data-demo-play]');
  const status = element.querySelector('[data-demo-status]');
  if (!audio || !button || audio.dataset.bound) return;
  audio.dataset.bound = 'true';
  let round = 1, started = false, finished = false, context;
  const send = (phase) => {
    if (!audio.isConnected) return;
    const input = document.querySelector('#demo-audio-event textarea, #demo-audio-event input');
    if (!input) return;
    input.value = `${audio.dataset.session}|${audio.dataset.passage}|${phase}`;
    const host = document.getElementById('demo-audio-confirm');
    const bridge = host && (host.querySelector('button') || host);
    if (bridge) bridge.click();
  };
  const retry = () => {
    status.textContent = 'Playback paused. Select Continue listening to finish this play.';
    button.textContent = 'Continue listening';
    button.disabled = false;
    button.hidden = false;
  };
  const play = async () => {
    if (finished) return;
    button.disabled = true;
    try {
      context ??= new AudioContext();
      await context.resume();
      if (context.state !== 'running') throw new Error('Audio is blocked');
      await audio.play();
    } catch (_) { retry(); }
  };
  button.addEventListener('click', play);
  audio.addEventListener('playing', () => {
    button.hidden = true;
    status.textContent = `Listen ${round} of 2`;
    if (!started) { started = true; send(`start${round}`); }
  });
  audio.addEventListener('pause', () => {
    if (!audio.ended && !finished) retry();
  });
  audio.addEventListener('error', retry);
  audio.addEventListener('ended', async () => {
    if (finished) return;
    send(`end${round}`);
    if (round === 2) {
      finished = true;
      status.textContent = 'Both listens complete. Submit your answers when ready.';
      button.hidden = true;
      audio.removeAttribute('src');
      return;
    }
    status.textContent = 'A beep signals the second listen.';
    // The context was unlocked by the learner's initial click. A quiet,
    // tapered 880 Hz tone separates two unmodified plays of the recording.
    const tone = context.createOscillator();
    const gain = context.createGain();
    tone.frequency.value = 880;
    tone.connect(gain); gain.connect(context.destination);
    const at = context.currentTime + 0.35;
    gain.gain.setValueAtTime(0, at);
    gain.gain.linearRampToValueAtTime(0.12, at + 0.02);
    gain.gain.setValueAtTime(0.12, at + 0.33);
    gain.gain.linearRampToValueAtTime(0, at + 0.35);
    tone.start(at); tone.stop(at + 0.36);
    tone.onended = () => {
      tone.disconnect(); gain.disconnect();
      setTimeout(() => {
        if (!audio.isConnected) return;
        round = 2; started = false; audio.currentTime = 0;
        play();
      }, 500);
    };
  });
};
if (element.demoObserver) element.demoObserver.disconnect();
element.demoObserver = new MutationObserver(bind);
element.demoObserver.observe(element, {childList: true, subtree: true});
bind();
