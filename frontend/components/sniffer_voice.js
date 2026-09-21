/**
 * Volkswagen Sniffer - Speech Synthesis and Lip-Sync Manager.
 * 
 * Manages Text-to-Speech (Web Speech API) in Polish, German, and English,
 * cleans chat text (markdown, emojis, units), and drives SnifferAvatar lip-sync
 * and eyebrow kinematics in real time.
 */

(function(window) {
    'use strict';

    const STORAGE_KEY_VOICE = 'vw_sniffer_voice_enabled';
    const STORAGE_KEY_RATE = 'vw_sniffer_voice_rate';

    // Unit expansions for natural speech
    const UNIT_EXPANSIONS = {
        pl: [
            { regex: /\b(\d+)\s*km\b/gi, replace: '$1 kilometrów' },
            { regex: /\b1\s*km\b/gi, replace: '1 kilometr' },
            { regex: /\b(\d+)\s*h\b/gi, replace: '$1 godzin' },
            { regex: /\b1\s*h\b/gi, replace: '1 godzina' },
            { regex: /\b(\d+)\s*godz\b/gi, replace: '$1 godzin' },
            { regex: /\b(\d+)\s*min\b/gi, replace: '$1 minut' },
            { regex: /\b(\d+)\s*(?:EUR|eur|€)\b/gi, replace: '$1 euro' },
            { regex: /\bVW\b/g, replace: 'Volkswagen' },
        ],
        de: [
            { regex: /\b(\d+)\s*km\b/gi, replace: '$1 Kilometer' },
            { regex: /\b1\s*km\b/gi, replace: '1 Kilometer' },
            { regex: /\b(\d+)\s*h\b/gi, replace: '$1 Stunden' },
            { regex: /\b1\s*h\b/gi, replace: '1 Stunde' },
            { regex: /\b(\d+)\s*min\b/gi, replace: '$1 Minuten' },
            { regex: /\b(\d+)\s*(?:EUR|eur|€)\b/gi, replace: '$1 Euro' },
            { regex: /\bVW\b/g, replace: 'Volkswagen' },
        ],
        en: [
            { regex: /\b(\d+)\s*km\b/gi, replace: '$1 kilometers' },
            { regex: /\b1\s*km\b/gi, replace: '1 kilometer' },
            { regex: /\b(\d+)\s*h\b/gi, replace: '$1 hours' },
            { regex: /\b1\s*h\b/gi, replace: '1 hour' },
            { regex: /\b(\d+)\s*min\b/gi, replace: '$1 minutes' },
            { regex: /\b(\d+)\s*(?:EUR|eur|€)\b/gi, replace: '$1 euros' },
            { regex: /\bVW\b/g, replace: 'Volkswagen' },
        ],
    };

    class SnifferVoiceManager {
        constructor() {
            this.synth = window.speechSynthesis || null;
            this.voices = [];
            this.activeUtterance = null;
            this.activeMessageId = null;
            this.registeredAvatars = new Set();
            this.messageAvatars = new Map();
            this.isSpeaking = false;
            this.currentAudio = null;
            this.audioContext = null;
            this.audioAnimFrame = null;

            // Load saved preferences (Default: voice enabled)
            const savedVoice = localStorage.getItem(STORAGE_KEY_VOICE);
            this.enabled = savedVoice !== null ? savedVoice === 'true' : true;

            const savedRate = localStorage.getItem(STORAGE_KEY_RATE);
            this.rate = savedRate ? parseFloat(savedRate) : 0.95;
            this.pitch = 0.80; // Deep, resonant masculine tone

            this.initVoices();
        }

        initVoices() {
            if (!this.synth) return;

            const updateVoices = () => {
                this.voices = this.synth.getVoices();
            };

            updateVoices();
            if (this.synth.onvoiceschanged !== undefined) {
                this.synth.onvoiceschanged = updateVoices;
            }
        }

        /**
         * Register a SnifferAvatar instance to automatically receive lip-sync events.
         * @param {SnifferAvatar} avatar
         */
        registerAvatar(avatar) {
            if (avatar && typeof avatar.setSpeaking === 'function') {
                this.registeredAvatars.add(avatar);
            }
        }

        /**
         * Unregister a SnifferAvatar.
         * @param {SnifferAvatar} avatar
         */
        unregisterAvatar(avatar) {
            this.registeredAvatars.delete(avatar);
        }

        /**
         * Register a message-specific SnifferAvatar instance.
         * @param {string} messageId
         * @param {SnifferAvatar} avatar
         */
        registerMessageAvatar(messageId, avatar) {
            if (messageId && avatar && typeof avatar.setSpeaking === 'function') {
                this.messageAvatars.set(messageId, avatar);
            }
        }

        /**
         * Unregister a message-specific SnifferAvatar instance.
         * @param {string} messageId
         */
        unregisterMessageAvatar(messageId) {
            if (messageId) {
                this.messageAvatars.delete(messageId);
            }
        }

        isVoiceEnabled() {
            return this.enabled;
        }

        setVoiceEnabled(enabled) {
            this.enabled = Boolean(enabled);
            localStorage.setItem(STORAGE_KEY_VOICE, String(this.enabled));
            if (!this.enabled && this.isSpeaking) {
                this.stop();
            }
            this.dispatchVoiceStateChange();
            return this.enabled;
        }

        toggleVoice() {
            return this.setVoiceEnabled(!this.enabled);
        }

        setRate(rate) {
            this.rate = Math.max(0.7, Math.min(1.5, rate));
            localStorage.setItem(STORAGE_KEY_RATE, String(this.rate));
        }

        dispatchVoiceStateChange() {
            window.dispatchEvent(new CustomEvent('sniffer-voice-state-change', {
                detail: {
                    enabled: this.enabled,
                    isSpeaking: this.isSpeaking,
                    activeMessageId: this.activeMessageId,
                }
            }));
        }

        /**
         * Clean chat text for natural speech synthesis.
         * Removes markdown, emojis, HTML/XML tags, and expands campervan units.
         * @param {string} text
         * @param {string} [lang='pl']
         * @returns {string}
         */
        cleanText(text, lang = 'pl') {
            if (!text) return '';

            let clean = text;

            // 1. Remove machine-readable <slot_state> tags and other XML/HTML tags
            clean = clean.replace(/<slot_state>[\s\S]*?<\/slot_state>/gi, '');
            clean = clean.replace(/<[^>]+>/g, ' ');

            // 2. Remove code fences and inline code
            clean = clean.replace(/```[\s\S]*?```/g, '');
            clean = clean.replace(/`([^`]+)`/g, '$1');

            // 3. Remove Markdown links [text](url) -> text, and images ![alt](url) -> ''
            clean = clean.replace(/!\[.*?\]\(.*?\)/g, '');
            clean = clean.replace(/\[(.*?)\]\(.*?\)/g, '$1');

            // 4. Remove Markdown headers (#, ##, etc.)
            clean = clean.replace(/^#{1,6}\s+/gm, '');

            // 5. Remove Markdown bold/italic
            clean = clean.replace(/\*{1,3}(.*?)\*{1,3}/g, '$1');
            clean = clean.replace(/_{1,3}(.*?)_{1,3}/g, '$1');

            // 6. Remove list bullets
            clean = clean.replace(/^\s*[-*+•]\s+/gm, '');

            // 7. Expand units for language
            const langKey = (lang || 'pl').toLowerCase();
            const expansions = UNIT_EXPANSIONS[langKey] || UNIT_EXPANSIONS.pl;
            for (const item of expansions) {
                clean = clean.replace(item.regex, item.replace);
            }

            // 8. Strip emojis and special graphic symbols
            clean = clean.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2B50}-\u{2B55}\u{FE00}-\u{FE0F}]/gu, '');

            // 9. Normalize whitespace and punctuation
            clean = clean.replace(/\s+/g, ' ');
            clean = clean.replace(/\s*([.,?!;:])\s*/g, '$1 ');
            clean = clean.trim();

            return clean;
        }

        /**
         * Select best voice for target language.
         * Prioritizes deep, natural masculine voices across PL, DE, and EN.
         * @param {string} lang
         * @returns {SpeechSynthesisVoice|null}
         */
        getBestVoice(lang = 'pl') {
            if (!this.voices || this.voices.length === 0) {
                if (this.synth) this.voices = this.synth.getVoices();
            }

            const langPrefix = (lang || 'pl').toLowerCase().slice(0, 2);
            const candidates = this.voices.filter(v => v.lang.toLowerCase().startsWith(langPrefix));
            if (candidates.length === 0) return null;

            // Preferred masculine voice names
            const preferredMap = {
                pl: ['marek', 'krzysztof', 'jan', 'jacek', 'google polski'],
                de: ['conrad', 'stefan', 'markus', 'florian', 'google deutsch'],
                en: ['guy', 'christopher', 'george', 'david', 'google us english'],
            };

            const preferred = preferredMap[langPrefix] || [];
            for (const pref of preferred) {
                const match = candidates.find(v => v.name.toLowerCase().includes(pref));
                if (match) return match;
            }

            // Filter out common female voice names to preserve deep male persona
            const femaleTokens = ['zofia', 'paulina', 'ewa', 'agata', 'maja', 'anna', 'katja', 'hedda', 'marlene', 'jenny', 'aria', 'samantha', 'zira', 'victoria', 'karen', 'susan', 'female'];
            const maleCandidates = candidates.filter(v => {
                const lower = v.name.toLowerCase();
                return !femaleTokens.some(token => lower.includes(token));
            });

            if (maleCandidates.length > 0) {
                return maleCandidates[0];
            }

            // Fallback to first voice for this language
            return candidates[0];
        }

        /**
         * Detect emotional sentiment from text content.
         * @param {string} text
         * @returns {'happy'|'curious'|'calm'|'excited'}
         */
        detectEmotion(text) {
            if (!text) return 'calm';
            const lower = text.toLowerCase();
            if (lower.includes('?') || /\b(dokąd|gdzie|kiedy|jak|wolisz|czy|który|wybrać)\b/i.test(lower)) {
                return 'curious';
            }
            if (lower.includes('!') || /\b(super|wspania|idealn|świetn|polecam|cudown|gotowe|cześć|hej|witaj|ruszamy)\b/i.test(lower)) {
                return 'happy';
            }
            return 'calm';
        }

        /**
         * Speak text using high-fidelity Neural TTS (ElevenLabs / OpenAI Onyx) with Web Speech API fallback.
         * Drives real-time lip-sync and eyebrow kinematics via Web Audio API amplitude analysis.
         * @param {string} text - Raw or cleaned text to speak.
         * @param {Object} [options={}]
         * @param {string} [options.lang='pl'] - Language code.
         * @param {string|number} [options.messageId=null] - Optional message identifier.
         * @param {string} [options.emotion=null] - Optional explicit emotion ('happy'|'curious'|'calm'|'excited').
         * @param {Function} [options.onStart=null]
         * @param {Function} [options.onEnd=null]
         */
        async speak(text, options = {}) {
            // Always stop any ongoing speech first
            this.stop();

            const lang = options.lang || (window.currentLang || 'pl');
            const clean = this.cleanText(text, lang);
            if (!clean) return;

            this.activeMessageId = options.messageId || null;
            const emotion = options.emotion || this.detectEmotion(text);

            // Apply emotional posture to all target avatars
            this.registeredAvatars.forEach(av => av.setEmotion && av.setEmotion(emotion));
            if (this.activeMessageId && this.messageAvatars.has(this.activeMessageId)) {
                const av = this.messageAvatars.get(this.activeMessageId);
                if (av.setEmotion) av.setEmotion(emotion);
            }
            if (this.activeMessageId && this.messageAvatars.has(`${this.activeMessageId}-map`)) {
                const av = this.messageAvatars.get(`${this.activeMessageId}-map`);
                if (av.setEmotion) av.setEmotion(emotion);
            }

            // 1. Try High-Fidelity Neural TTS via backend (/api/tts/speak)
            try {
                const res = await fetch('/api/tts/speak', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: clean,
                        lang: lang,
                        voice: 'onyx'
                    })
                });

                if (res.ok) {
                    const blob = await res.blob();
                    const audioUrl = URL.createObjectURL(blob);
                    this.playNeuralAudio(audioUrl, Object.assign({}, options, { emotion }));
                    return;
                }
            } catch (err) {
                console.warn('[SnifferVoice] Neural TTS backend unavailable, falling back to Web Speech API:', err);
            }

            // 2. Fallback to Web Speech API
            this.speakWebSpeech(clean, Object.assign({}, options, { emotion }));
        }

        playNeuralAudio(audioUrl, options = {}) {
            const audio = new Audio(audioUrl);
            this.currentAudio = audio;
            const emotion = options.emotion || 'calm';

            audio.onplay = () => {
                this.isSpeaking = true;
                this.registeredAvatars.forEach(av => {
                    if (av.setEmotion) av.setEmotion(emotion);
                    av.setSpeaking(true);
                });
                if (this.activeMessageId && this.messageAvatars.has(this.activeMessageId)) {
                    const av = this.messageAvatars.get(this.activeMessageId);
                    if (av.setEmotion) av.setEmotion(emotion);
                    av.setSpeaking(true);
                }
                if (this.activeMessageId && this.messageAvatars.has(`${this.activeMessageId}-map`)) {
                    const av = this.messageAvatars.get(`${this.activeMessageId}-map`);
                    if (av.setEmotion) av.setEmotion(emotion);
                    av.setSpeaking(true);
                }
                this.dispatchVoiceStateChange();
                if (typeof options.onStart === 'function') options.onStart();

                // Setup Web Audio API Analyser for real-time lip-sync & phoneme shapes
                this.setupAudioAnalysis(audio);
            };

            const cleanup = () => {
                this.isSpeaking = false;
                const finishedMsgId = this.activeMessageId;
                this.activeMessageId = null;
                if (this.audioAnimFrame) {
                    cancelAnimationFrame(this.audioAnimFrame);
                    this.audioAnimFrame = null;
                }
                if (this.currentAudio === audio) {
                    this.currentAudio = null;
                }
                try {
                    URL.revokeObjectURL(audioUrl);
                } catch (e) {}

                this.registeredAvatars.forEach(av => {
                    av.setSpeaking(false);
                    if (av.setEmotion) av.setEmotion(emotion);
                });
                this.messageAvatars.forEach(av => {
                    av.setSpeaking(false);
                    if (av.setEmotion) av.setEmotion(emotion);
                });
                this.dispatchVoiceStateChange();
                if (typeof options.onEnd === 'function') options.onEnd();
            };

            audio.onended = cleanup;
            audio.onerror = (e) => {
                console.warn('[SnifferVoice] Audio playback error, trying fallback:', e);
                cleanup();
            };

            audio.play().catch(err => {
                console.warn('[SnifferVoice] Autoplay prevented or error:', err);
                cleanup();
            });
        }

        setupAudioAnalysis(audio) {
            try {
                if (!this.audioContext) {
                    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                    if (AudioContextClass) {
                        this.audioContext = new AudioContextClass();
                    }
                }
                if (!this.audioContext) return;

                if (this.audioContext.state === 'suspended') {
                    this.audioContext.resume();
                }

                let source;
                try {
                    source = this.audioContext.createMediaElementSource(audio);
                } catch (e) {
                    return;
                }

                const analyser = this.audioContext.createAnalyser();
                analyser.fftSize = 256;
                source.connect(analyser);
                analyser.connect(this.audioContext.destination);

                const bufferLength = analyser.frequencyBinCount;
                const dataArray = new Uint8Array(bufferLength);

                const analyzeLoop = () => {
                    if (!this.isSpeaking || !this.currentAudio) {
                        return;
                    }
                    analyser.getByteFrequencyData(dataArray);

                    // Multi-band analysis:
                    // 1. Low frequencies (bins 1-8: 150Hz - 1.2kHz): Vowel cavity & vertical jaw drop
                    let lowSum = 0;
                    const lowBins = 8;
                    for (let i = 1; i <= lowBins; i++) {
                        lowSum += dataArray[i];
                    }
                    const lowAvg = lowSum / lowBins;
                    const normalizedLow = Math.min(1.0, lowAvg / 50);

                    // 2. High frequencies (bins 10-26: 1.5kHz - 4kHz): Sibilants/consonants & horizontal smile stretch
                    let highSum = 0;
                    const highBins = 16;
                    for (let i = 10; i < 10 + highBins; i++) {
                        highSum += dataArray[i];
                    }
                    const highAvg = highSum / highBins;
                    const normalizedHigh = Math.min(1.0, highAvg / 45);

                    // 3. Overall amplitude
                    let totalSum = 0;
                    for (let i = 0; i < bufferLength; i++) {
                        totalSum += dataArray[i];
                    }
                    const avg = totalSum / bufferLength;
                    const normalizedTotal = Math.min(1.0, avg / 55);

                    const mouthOpen = normalizedLow > 0.10 ? (0.22 + normalizedLow * 0.78) : 0.0;
                    const mouthWidth = 0.96 + (normalizedHigh * 0.16); // Dynamic phoneme width
                    const browLift = 0.35 + normalizedTotal * 0.45;

                    this.registeredAvatars.forEach(av => av.pulseSpeech(mouthOpen, browLift, mouthWidth));
                    if (this.activeMessageId && this.messageAvatars.has(this.activeMessageId)) {
                        this.messageAvatars.get(this.activeMessageId).pulseSpeech(mouthOpen, browLift, mouthWidth);
                    }
                    if (this.activeMessageId && this.messageAvatars.has(`${this.activeMessageId}-map`)) {
                        this.messageAvatars.get(`${this.activeMessageId}-map`).pulseSpeech(mouthOpen, browLift, mouthWidth);
                    }

                    this.audioAnimFrame = requestAnimationFrame(analyzeLoop);
                };

                this.audioAnimFrame = requestAnimationFrame(analyzeLoop);
            } catch (err) {
                console.warn('[SnifferVoice] Audio analysis setup error:', err);
            }
        }

        /**
         * Fallback speech synthesis using Web Speech API.
         */
        speakWebSpeech(clean, options = {}) {
            if (!this.synth) {
                console.warn('[SnifferVoice] Web Speech API not supported.');
                return;
            }

            const lang = options.lang || (window.currentLang || 'pl');
            const utterance = new SpeechSynthesisUtterance(clean);
            utterance.rate = this.rate;
            utterance.pitch = this.pitch;
            utterance.lang = lang === 'de' ? 'de-DE' : (lang === 'en' ? 'en-US' : 'pl-PL');

            const voice = this.getBestVoice(lang);
            if (voice) {
                utterance.voice = voice;
            }

            this.activeUtterance = utterance;

            const emotion = options.emotion || 'calm';

            utterance.onstart = () => {
                this.isSpeaking = true;
                this.registeredAvatars.forEach(av => {
                    if (av.setEmotion) av.setEmotion(emotion);
                    av.setSpeaking(true);
                });
                if (this.activeMessageId && this.messageAvatars.has(this.activeMessageId)) {
                    const av = this.messageAvatars.get(this.activeMessageId);
                    if (av.setEmotion) av.setEmotion(emotion);
                    av.setSpeaking(true);
                }
                if (this.activeMessageId && this.messageAvatars.has(`${this.activeMessageId}-map`)) {
                    const av = this.messageAvatars.get(`${this.activeMessageId}-map`);
                    if (av.setEmotion) av.setEmotion(emotion);
                    av.setSpeaking(true);
                }
                this.dispatchVoiceStateChange();
                if (typeof options.onStart === 'function') options.onStart();
            };

            utterance.onboundary = (event) => {
                if (!this.isSpeaking) return;

                const charIdx = event.charIndex;
                const remaining = clean.slice(charIdx);
                const wordMatch = remaining.match(/^(\S+)/);
                const currentWord = wordMatch ? wordMatch[1] : '';

                const isQuestion = currentWord.includes('?') || remaining.startsWith('?');
                const isExclamation = currentWord.includes('!') || remaining.startsWith('!');

                let eyebrowLift = 0.45;
                if (isQuestion) {
                    eyebrowLift = 0.95;
                } else if (isExclamation) {
                    eyebrowLift = 0.85;
                } else if (Math.random() > 0.6) {
                    eyebrowLift = 0.65;
                }

                const mouthOpen = 0.5 + Math.min(0.5, (currentWord.length * 0.08));
                const mouthWidth = 0.95 + (isExclamation ? 0.15 : 0.05);

                this.registeredAvatars.forEach(av => {
                    av.pulseSpeech(mouthOpen, eyebrowLift, mouthWidth);
                });
                if (this.activeMessageId && this.messageAvatars.has(this.activeMessageId)) {
                    this.messageAvatars.get(this.activeMessageId).pulseSpeech(mouthOpen, eyebrowLift, mouthWidth);
                }
                if (this.activeMessageId && this.messageAvatars.has(`${this.activeMessageId}-map`)) {
                    this.messageAvatars.get(`${this.activeMessageId}-map`).pulseSpeech(mouthOpen, eyebrowLift, mouthWidth);
                }

                // Decay mouth back to closed after word duration
                const wordDuration = Math.max(140, Math.min(500, currentWord.length * 65));
                setTimeout(() => {
                    if (this.isSpeaking) {
                        this.registeredAvatars.forEach(av => av.pulseSpeech(0.0, 0.4, 1.0));
                        if (this.activeMessageId && this.messageAvatars.has(this.activeMessageId)) {
                            this.messageAvatars.get(this.activeMessageId).pulseSpeech(0.0, 0.4, 1.0);
                        }
                        if (this.activeMessageId && this.messageAvatars.has(`${this.activeMessageId}-map`)) {
                            this.messageAvatars.get(`${this.activeMessageId}-map`).pulseSpeech(0.0, 0.4, 1.0);
                        }
                    }
                }, wordDuration);
            };

            const cleanup = () => {
                this.isSpeaking = false;
                this.activeUtterance = null;
                const finishedMsgId = this.activeMessageId;
                this.activeMessageId = null;
                this.registeredAvatars.forEach(av => av.setSpeaking(false));
                this.messageAvatars.forEach(av => av.setSpeaking(false));
                this.dispatchVoiceStateChange();
                if (typeof options.onEnd === 'function') options.onEnd();
            };

            utterance.onend = cleanup;
            utterance.onerror = (err) => {
                if (err.error !== 'canceled') {
                    console.warn('[SnifferVoice] Web Speech error:', err);
                }
                cleanup();
            };

            this.synth.speak(utterance);
        }

        /**
         * Stop current speech immediately and reset avatar to idle.
         */
        stop() {
            if (this.currentAudio) {
                try {
                    this.currentAudio.pause();
                    this.currentAudio.currentTime = 0;
                    this.currentAudio.src = '';
                } catch (e) {}
                this.currentAudio = null;
            }
            if (this.audioAnimFrame) {
                cancelAnimationFrame(this.audioAnimFrame);
                this.audioAnimFrame = null;
            }
            if (this.synth) {
                this.synth.cancel();
            }
            this.isSpeaking = false;
            this.activeUtterance = null;
            const prevMessageId = this.activeMessageId;
            this.activeMessageId = null;
            this.registeredAvatars.forEach(av => av.setSpeaking(false));
            this.messageAvatars.forEach(av => av.setSpeaking(false));
            this.dispatchVoiceStateChange();
            return prevMessageId;
        }
    }

    // Expose singleton instance globally
    window.snifferVoice = new SnifferVoiceManager();
    window.SnifferVoiceManager = SnifferVoiceManager;

})(window);
