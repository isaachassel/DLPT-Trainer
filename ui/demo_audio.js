const bind = () => {
  // Gradio replaces the HTML component's inner host after a value update.
  // Resolve the live host instead of observing the detached js_on_load element.
  const host = document.getElementById('demo-audio-player');
  const audio = host?.querySelector('audio[data-demo-audio]');
  const button = host?.querySelector('[data-demo-play]');
  const status = host?.querySelector('[data-demo-status]');
  const key = audio && `${audio.dataset.session}|${audio.dataset.passage}`;
  const prior = document.demoAudioBinding;
  if (prior?.audio === audio && prior?.button === button && prior?.key === key) return;
  if (prior) { prior.dispose(); document.demoAudioBinding = null; }
  if (!audio || !button || !status) return;
  const controller = new AbortController();
  const options = {signal: controller.signal};
  let round = Number(audio.dataset.round || 1), started = audio.dataset.started === 'true';
  let finished = false, context, nextPlay;
  document.demoAudioBinding = {audio, button, key, dispose: () => {
    finished = true; controller.abort(); clearTimeout(nextPlay); audio.pause();
    if (context) context.close().catch(() => {});
  }};
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
  button.addEventListener('click', play, options);
  audio.addEventListener('playing', () => {
    button.hidden = true;
    status.textContent = `Listen ${round} of 2`;
    if (!started) { started = true; send(`start${round}`); }
  }, options);
  audio.addEventListener('pause', () => {
    if (!audio.ended && !finished) retry();
  }, options);
  audio.addEventListener('error', retry, options);
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
      nextPlay = setTimeout(() => {
        if (finished || !audio.isConnected) return;
        round = 2; started = false; audio.currentTime = 0;
        play();
      }, 500);
    };
  }, options);
};
if (document.demoAudioObserver) document.demoAudioObserver.disconnect();
document.demoAudioObserver = new MutationObserver(bind);
document.demoAudioObserver.observe(document.body, {
  childList: true, subtree: true, attributes: true,
  attributeFilter: ['data-passage', 'data-session']
});
bind();
