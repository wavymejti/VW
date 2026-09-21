/**
 * Volkswagen Sniffer - Photographic Face Rigging & Emotional Expression Component.
 * 
 * Uses the exact 3D-rendered mascot photo (sniffer-avatar.png) and animates
 * its photographic facial elements using second-order Spring-Damper physics:
 * - Expressive emotional states (HAPPY, CURIOUS, CALM, EXCITED)
 * - Iconic canine head tilt around anatomical neck pivot
 * - Audio-reactive phoneme mouth shapes (vertical opening vs. smile stretch)
 * - Asymmetric inquisitive eyebrow elevation & tilt
 * - Warm smiling eye squints (Duchenne smile) and natural blinking
 * - Secondary floppy ear physics trailing head movements
 * 
 * Complies with VW California brand guidelines and user specifications.
 */

(function(window) {
    'use strict';

    let avatarInstanceCounter = 0;

    // 240-frame normalized mouth aperture lookup table for sniffer_talking.mp4 (24 FPS, 10.0s)
    // 0.0 = completely closed, 1.0 = maximum open aperture.
    const FRAME_APERTURES = [
        0.67, 0.68, 0.69, 0.70, 0.73, 0.72, 0.75, 0.76, 0.78, 0.76, 0.79, 0.80, 0.82, 0.80, 0.81, 0.81, 0.83, 0.80, 0.81, 0.80,
        0.81, 0.80, 0.82, 0.79, 0.80, 0.74, 0.68, 0.60, 0.60, 0.58, 0.50, 0.45, 0.46, 0.47, 0.48, 0.48, 0.48, 0.51, 0.56, 0.53,
        0.47, 0.43, 0.42, 0.42, 0.42, 0.42, 0.42, 0.44, 0.44, 0.32, 0.00, 0.08, 0.39, 0.46, 0.47, 0.53, 0.59, 0.40, 0.20, 0.19,
        0.26, 0.31, 0.55, 0.91, 1.00, 0.93, 0.57, 0.28, 0.18, 0.27, 0.45, 0.62, 0.69, 0.68, 0.70, 0.70, 0.71, 0.68, 0.54, 0.39,
        0.37, 0.37, 0.39, 0.38, 0.39, 0.21, 0.14, 0.12, 0.14, 0.16, 0.22, 0.33, 0.40, 0.49, 0.49, 0.39, 0.37, 0.48, 0.41, 0.33,
        0.21, 0.14, 0.11, 0.15, 0.27, 0.47, 0.28, 0.15, 0.05, 0.33, 0.40, 0.26, 0.08, 0.41, 0.39, 0.37, 0.32, 0.05, 0.12, 0.11,
        0.12, 0.13, 0.17, 0.22, 0.29, 0.34, 0.39, 0.42, 0.44, 0.41, 0.36, 0.32, 0.28, 0.15, 0.17, 0.26, 0.43, 0.38, 0.39, 0.37,
        0.50, 0.59, 0.52, 0.37, 0.24, 0.24, 0.26, 0.37, 0.52, 0.57, 0.58, 0.52, 0.44, 0.30, 0.27, 0.25, 0.12, 0.13, 0.27, 0.24,
        0.21, 0.09, 0.20, 0.58, 0.57, 0.31, 0.17, 0.09, 0.03, 0.19, 0.19, 0.17, 0.26, 0.16, 0.09, 0.10, 0.11, 0.16, 0.19, 0.18,
        0.20, 0.19, 0.20, 0.19, 0.19, 0.18, 0.20, 0.19, 0.17, 0.19, 0.07, 0.03, 0.10, 0.27, 0.39, 0.57, 0.56, 0.48, 0.38, 0.26,
        0.39, 0.75, 0.86, 0.84, 0.71, 0.35, 0.28, 0.51, 0.65, 0.46, 0.29, 0.26, 0.46, 0.77, 0.91, 0.91, 0.89, 0.86, 0.74, 0.59,
        0.56, 0.54, 0.56, 0.56, 0.57, 0.55, 0.56, 0.55, 0.56, 0.55, 0.56, 0.55, 0.56, 0.56, 0.57, 0.56, 0.56, 0.55, 0.55, 0.55
    ];

    /**
     * Spring-Damper (Second-Order Dynamics) physics simulator.
     * Provides natural inertia, organic overshoot, and soft elastic damping.
     */
    class Spring {
        constructor(val = 0, stiffness = 160, damping = 16, mass = 1) {
            this.val = val;
            this.target = val;
            this.vel = 0;
            this.stiffness = stiffness;
            this.damping = damping;
            this.mass = mass;
        }

        set(v) {
            this.val = v;
            this.target = v;
            this.vel = 0;
        }

        setTarget(t) {
            this.target = t;
        }

        update(dt = 0.016) {
            const safeDt = Math.min(0.033, Math.max(0.001, dt));
            const force = -this.stiffness * (this.val - this.target);
            const dampingForce = -this.damping * this.vel;
            const accel = (force + dampingForce) / this.mass;
            this.vel += accel * safeDt;
            this.val += this.vel * safeDt;
            return this.val;
        }
    }

    class SnifferAvatar {
        /**
         * @param {HTMLElement|string} container - DOM element or selector to mount avatar.
         * @param {Object} options - Configuration options.
         * @param {number} [options.size=48] - Pixel width/height of the avatar.
         * @param {boolean} [options.interactive=true] - Respond to hover/click.
         * @param {boolean} [options.autoBlink=true] - Run automatic blink loop.
         * @param {string} [options.className=''] - Additional CSS classes.
         */
        constructor(container, options = {}) {
            this.container = typeof container === 'string' ? document.querySelector(container) : container;
            if (!this.container) {
                console.warn('[SnifferAvatar] Target container not found.');
                return;
            }

            this.instanceId = ++avatarInstanceCounter;
            this.options = Object.assign({
                size: 48,
                mode: 'video', // 'video' (Cinematic 3D Video Avatar) or 'rig' (2.5D Spring Rig)
                videoSrc: '/static/assets/video/sniffer_talking.mp4',
                posterSrc: '/static/assets/video/sniffer_idle_poster.jpg',
                interactive: true,
                autoBlink: true,
                className: '',
            }, options);

            // States
            this.isSpeaking = false;
            this.isThinking = false;
            this.currentEmotion = 'calm'; // 'calm' | 'happy' | 'curious' | 'excited'

            // Springs for organic physical motion (used in 'rig' mode and as physics controller)
            this.springMouthOpen = new Spring(0.0, 240, 18);
            this.springMouthWidth = new Spring(1.0, 180, 16);
            this.springBrowLeft = new Spring(0.0, 140, 14);
            this.springBrowRight = new Spring(0.0, 140, 14);
            this.springBrowTilt = new Spring(0.0, 120, 14);
            this.springHeadAngle = new Spring(0.0, 85, 12);
            this.springHeadY = new Spring(0.0, 95, 13);
            this.springHeadX = new Spring(0.0, 80, 12);
            this.springEarLeft = new Spring(0.0, 110, 11);
            this.springEarRight = new Spring(0.0, 110, 11);
            this.springEyeSquint = new Spring(0.0, 130, 15);

            // Timers & Loops
            this.blinkTimer = null;
            this.animFrame = null;
            this.speechInterval = null;
            this.lastFrameTime = performance.now();

            this.render();
            this.bindElements();
            if (this.options.mode === 'rig') {
                if (this.options.autoBlink) {
                    this.startBlinkLoop();
                }
                this.startPhysicsLoop();
            }
        }

        render() {
            const size = this.options.size;
            const id = this.instanceId;
            const wrapper = document.createElement('div');
            wrapper.className = `sniffer-avatar-wrap ${this.options.className}`.trim();
            wrapper.style.width = `${size}px`;
            wrapper.style.height = `${size}px`;
            wrapper.setAttribute('role', 'img');
            wrapper.setAttribute('aria-label', 'Volkswagen Sniffer Avatar');

            // 1. Cinematic 3D Video Mode
            if (this.options.mode === 'video') {
                wrapper.innerHTML = `
                    <video class="sniffer-avatar-video" playsinline muted loop preload="auto" poster="${this.options.posterSrc}">
                        <source src="${this.options.videoSrc}" type="video/mp4">
                    </video>
                `;
                this.container.innerHTML = '';
                this.container.appendChild(wrapper);
                this.wrapper = wrapper;
                this.elVideo = wrapper.querySelector('video');
                if (this.elVideo) {
                    // Initialize at Frame 50 (2.083s) where mouth is naturally closed with a warm resting smile
                    this.elVideo.currentTime = 2.083;
                    this.elVideo.addEventListener('loadedmetadata', () => {
                        this.elVideo.currentTime = 2.083;
                    });
                    this.elVideo.onerror = () => {
                        console.warn('[SnifferAvatar] Video failed to load, falling back to 2.5D rig');
                        this.options.mode = 'rig';
                        this.render();
                        this.bindElements();
                        this.startPhysicsLoop();
                    };
                }
                return;
            }

            // 2. 2.5D Spring-Damper Photographic Rig Fallback
            wrapper.innerHTML = `
                <svg class="sniffer-avatar-svg" viewBox="172 100 680 680" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="overflow:visible;">
                    <defs>
                        <!-- Eyelid clips for natural blinking & squints over the exact eyes -->
                        <clipPath id="snf-left-eye-clip-${id}">
                            <ellipse cx="460" cy="255" rx="46" ry="52"/>
                        </clipPath>
                        <clipPath id="snf-right-eye-clip-${id}">
                            <ellipse cx="595" cy="255" rx="46" ry="52"/>
                        </clipPath>
                    </defs>

                    <!-- Root Head Group rotating around anatomical neck pivot (cx=512, cy=820) -->
                    <g class="snf-photo-root" id="snf-photo-root-${id}" style="transform-origin: 512px 820px;">
                        
                        <!-- 1. BASE IMAGE: The EXACT photographic 3D render of Sniffer -->
                        <image href="/static/assets/sniffer-avatar.png" x="0" y="0" width="1024" height="902" preserveAspectRatio="xMidYMid meet"/>

                        <!-- 2. FLOPPY EARS (Soft secondary spring motion) -->
                        <g class="snf-photo-ear-left" id="snf-photo-ear-left-${id}" style="transform-origin: 320px 220px;">
                            <image href="/static/assets/sniffer-ear-left.png" x="60" y="180" width="300" height="440"/>
                        </g>
                        <g class="snf-photo-ear-right" id="snf-photo-ear-right-${id}" style="transform-origin: 700px 220px;">
                            <image href="/static/assets/sniffer-ear-right.png" x="660" y="180" width="300" height="440"/>
                        </g>

                        <!-- 3. SMILING EYE SQUINTS (Duchenne smile lower eyelid curve) -->
                        <g class="snf-photo-eye-squints" id="snf-photo-eye-squints-${id}">
                            <g clip-path="url(#snf-left-eye-clip-${id})">
                                <ellipse id="snf-squint-left-${id}" cx="460" cy="302" rx="48" ry="36" fill="#E8EEF5" style="opacity:0; transform-origin: 460px 302px; transform: scaleY(0);"/>
                            </g>
                            <g clip-path="url(#snf-right-eye-clip-${id})">
                                <ellipse id="snf-squint-right-${id}" cx="595" cy="302" rx="48" ry="36" fill="#E8EEF5" style="opacity:0; transform-origin: 595px 302px; transform: scaleY(0);"/>
                            </g>
                        </g>

                        <!-- 4. BLINKING EYELIDS (Natural eyelid blink) -->
                        <g class="snf-photo-eyelids" id="snf-photo-eyelids-${id}">
                            <g clip-path="url(#snf-left-eye-clip-${id})">
                                <ellipse id="snf-eyelid-left-${id}" cx="460" cy="210" rx="55" ry="55" fill="#E8EEF5" stroke="#CBD5E1" stroke-width="2" style="opacity:0; transform-origin: 460px 210px; transform: scaleY(0);"/>
                            </g>
                            <g clip-path="url(#snf-right-eye-clip-${id})">
                                <ellipse id="snf-eyelid-right-${id}" cx="595" cy="210" rx="55" ry="55" fill="#E8EEF5" stroke="#CBD5E1" stroke-width="2" style="opacity:0; transform-origin: 595px 210px; transform: scaleY(0);"/>
                            </g>
                        </g>

                        <!-- 5. MOUTH INTERIOR CAVITY (Revealed with dynamic phoneme width/height) -->
                        <g class="snf-photo-mouth-cavity" id="snf-photo-mouth-cavity-${id}" style="opacity: 0; transform-origin: 512px 715px; transform: scaleY(0);">
                            <ellipse cx="512" cy="728" rx="66" ry="26" fill="#380d12"/>
                            <ellipse cx="512" cy="736" rx="40" ry="18" fill="#e15f73"/>
                            <polygon points="478,714 490,714 484,725" fill="#ffffff"/>
                            <polygon points="534,714 546,714 540,725" fill="#ffffff"/>
                        </g>

                        <!-- 6. PHOTOGRAPHIC JAW/CHIN (Moves down with spring elasticity) -->
                        <g class="snf-photo-jaw" id="snf-photo-jaw-${id}" style="transform-origin: 512px 740px;">
                            <image href="/static/assets/sniffer-jaw.png" x="410" y="710" width="204" height="65"/>
                        </g>

                        <!-- 7. PHOTOGRAPHIC MUZZLE OVERLAY (Blue nose & upper cheeks) -->
                        <g class="snf-photo-muzzle" id="snf-photo-muzzle-${id}" style="transform-origin: 512px 500px;">
                            <image href="/static/assets/sniffer-muzzle.png" x="280" y="310" width="460" height="408"/>
                        </g>

                        <!-- 8. PHOTOGRAPHIC EYEBROWS (Independent left & right spring kinematics) -->
                        <g class="snf-photo-brow-left" id="snf-photo-brow-left-${id}" style="transform-origin: 445px 185px;">
                            <image href="/static/assets/sniffer-brow-left.png" x="370" y="130" width="150" height="110"/>
                        </g>
                        <g class="snf-photo-brow-right" id="snf-photo-brow-right-${id}" style="transform-origin: 595px 185px;">
                            <image href="/static/assets/sniffer-brow-right.png" x="520" y="130" width="150" height="110"/>
                        </g>

                    </g>
                </svg>
            `;

            this.container.innerHTML = '';
            this.container.appendChild(wrapper);
            this.wrapper = wrapper;
        }

        bindElements() {
            const id = this.instanceId;
            this.elRoot = this.wrapper.querySelector(`#snf-photo-root-${id}`);
            this.elMouthCavity = this.wrapper.querySelector(`#snf-photo-mouth-cavity-${id}`);
            this.elJaw = this.wrapper.querySelector(`#snf-photo-jaw-${id}`);
            this.elMuzzle = this.wrapper.querySelector(`#snf-photo-muzzle-${id}`);
            this.elBrowLeft = this.wrapper.querySelector(`#snf-photo-brow-left-${id}`);
            this.elBrowRight = this.wrapper.querySelector(`#snf-photo-brow-right-${id}`);
            this.elEyelidLeft = this.wrapper.querySelector(`#snf-eyelid-left-${id}`);
            this.elEyelidRight = this.wrapper.querySelector(`#snf-eyelid-right-${id}`);
            this.elSquintLeft = this.wrapper.querySelector(`#snf-squint-left-${id}`);
            this.elSquintRight = this.wrapper.querySelector(`#snf-squint-right-${id}`);
            this.elEarLeft = this.wrapper.querySelector(`#snf-photo-ear-left-${id}`);
            this.elEarRight = this.wrapper.querySelector(`#snf-photo-ear-right-${id}`);

            if (this.options.interactive) {
                this.wrapper.style.cursor = 'pointer';
                this.wrapper.addEventListener('mouseenter', () => this.onHover(true));
                this.wrapper.addEventListener('mouseleave', () => this.onHover(false));
                this.wrapper.addEventListener('click', () => this.onClick());
            }
        }

        /**
         * Continuous Spring-Damper physics loop.
         */
        startPhysicsLoop() {
            const update = (now) => {
                const dt = (now - this.lastFrameTime) / 1000;
                this.lastFrameTime = now;

                // Update all physical springs
                this.springMouthOpen.update(dt);
                this.springMouthWidth.update(dt);
                this.springBrowLeft.update(dt);
                this.springBrowRight.update(dt);
                this.springBrowTilt.update(dt);
                this.springHeadAngle.update(dt);
                this.springHeadY.update(dt);
                this.springHeadX.update(dt);
                this.springEarLeft.update(dt);
                this.springEarRight.update(dt);
                this.springEyeSquint.update(dt);

                this.applyFacialTransforms();
                this.animFrame = requestAnimationFrame(update);
            };
            this.animFrame = requestAnimationFrame(update);
        }

        applyFacialTransforms() {
            if (!this.elMouthCavity || !this.elJaw) return;

            const open = Math.max(0, Math.min(1, this.springMouthOpen.val));
            const width = Math.max(0.85, Math.min(1.2, this.springMouthWidth.val));
            const browL = Math.max(0, Math.min(1, this.springBrowLeft.val));
            const browR = Math.max(0, Math.min(1, this.springBrowRight.val));
            const browTilt = this.springBrowTilt.val;
            const headAngle = this.springHeadAngle.val;
            const headY = this.springHeadY.val;
            const headX = this.springHeadX.val;
            const squint = Math.max(0, Math.min(1, this.springEyeSquint.val));

            // 1. Mouth Cavity & Jaw Kinematics
            if (open > 0.08) {
                this.elMouthCavity.style.display = 'block';
                this.elMouthCavity.style.opacity = String(Math.min(1, (open - 0.08) * 3.0));
                this.elMouthCavity.style.transform = `scaleY(${open * 1.5}) scaleX(${width})`;
                this.elJaw.style.transform = `translateY(${open * 36}px) scaleX(${1 + (width - 1) * 0.4})`;
            } else {
                this.elMouthCavity.style.display = 'none';
                this.elMouthCavity.style.opacity = '0';
                this.elMouthCavity.style.transform = 'scaleY(0)';
                this.elJaw.style.transform = `scaleX(${1 + (width - 1) * 0.3})`;
            }

            // 2. Eyebrows (Independent left & right spring elevation & tilt)
            const browLeftY = -browL * 34;
            const browRightY = -browR * 34;
            const leftRot = (browL * 7) + browTilt;
            const rightRot = (-browR * 7) - browTilt;

            if (this.elBrowLeft) {
                this.elBrowLeft.style.transform = `translateY(${browLeftY}px) rotate(${leftRot}deg)`;
            }
            if (this.elBrowRight) {
                this.elBrowRight.style.transform = `translateY(${browRightY}px) rotate(${rightRot}deg)`;
            }

            // 3. Smiling Duchenne Eye Squint
            if (this.elSquintLeft && this.elSquintRight) {
                if (squint > 0.05) {
                    this.elSquintLeft.style.opacity = String(squint * 0.95);
                    this.elSquintLeft.style.transform = `scaleY(${squint * 1.4})`;
                    this.elSquintRight.style.opacity = String(squint * 0.95);
                    this.elSquintRight.style.transform = `scaleY(${squint * 1.4})`;
                } else {
                    this.elSquintLeft.style.opacity = '0';
                    this.elSquintLeft.style.transform = 'scaleY(0)';
                    this.elSquintRight.style.opacity = '0';
                    this.elSquintRight.style.transform = 'scaleY(0)';
                }
            }

            // 4. Head Group (Canine Head Tilt + Speech Nodding + Lateral Shift)
            if (this.elRoot) {
                let currentHeadY = headY;
                // Subtle organic idle breathing when calm
                if (!this.isSpeaking && this.currentEmotion === 'calm') {
                    currentHeadY += Math.sin(Date.now() * 0.002) * 1.5;
                }
                this.elRoot.style.transform = `translate(${headX}px, ${currentHeadY}px) rotate(${headAngle}deg)`;
            }

            // 5. Floppy Ears (Secondary spring physics trailing head movement)
            const earLRot = this.springEarLeft.val + (-headAngle * 0.45);
            const earRRot = this.springEarRight.val + (-headAngle * 0.45);
            if (this.elEarLeft) {
                this.elEarLeft.style.transform = `rotate(${earLRot}deg)`;
            }
            if (this.elEarRight) {
                this.elEarRight.style.transform = `rotate(${earRRot}deg)`;
            }
        }

        /**
         * Set the mascot's emotional expression.
         * @param {'calm'|'happy'|'curious'|'excited'} emotion
         */
        setEmotion(emotion) {
            this.currentEmotion = emotion || 'calm';

            if (this.options.mode === 'video' && this.elVideo) {
                if (!this.isSpeaking) {
                    if (this.currentEmotion === 'happy' || this.currentEmotion === 'excited') {
                        this.elVideo.currentTime = 8.8; // Big beaming smile!
                    } else if (this.currentEmotion === 'curious') {
                        this.elVideo.currentTime = 1.8; // Curious head tilt & attentive gaze
                    } else {
                        this.elVideo.currentTime = 2.083; // Calm resting pose (Frame 50, closed mouth, warm smile)
                    }
                }
                return;
            }

            switch (this.currentEmotion) {
                case 'happy':
                    this.springHeadAngle.setTarget(3.2); // Cheerful slight tilt
                    this.springHeadX.setTarget(2.0);
                    this.springEyeSquint.setTarget(0.65); // Warm smiling eyes!
                    this.springBrowLeft.setTarget(0.72);
                    this.springBrowRight.setTarget(0.72);
                    this.springBrowTilt.setTarget(4.0);
                    this.springMouthWidth.setTarget(1.08); // Cheerful smile stretch
                    this.springEarLeft.setTarget(-2.5);
                    this.springEarRight.setTarget(2.5);
                    break;

                case 'curious':
                    this.springHeadAngle.setTarget(-5.5); // Iconic canine head tilt!
                    this.springHeadX.setTarget(-4.5);
                    this.springEyeSquint.setTarget(0.0);
                    this.springBrowLeft.setTarget(0.85); // Inquisitive brow asymmetry
                    this.springBrowRight.setTarget(0.25);
                    this.springBrowTilt.setTarget(-3.5);
                    this.springMouthWidth.setTarget(1.0);
                    this.springEarLeft.setTarget(-4.0); // Attentive perked ear
                    this.springEarRight.setTarget(1.5);
                    this.sniff();
                    break;

                case 'excited':
                    this.springHeadAngle.setTarget(-2.5);
                    this.springHeadX.setTarget(-1.5);
                    this.springEyeSquint.setTarget(0.45);
                    this.springBrowLeft.setTarget(0.90);
                    this.springBrowRight.setTarget(0.90);
                    this.springBrowTilt.setTarget(5.0);
                    this.springMouthWidth.setTarget(1.12);
                    this.springEarLeft.setTarget(-3.5);
                    this.springEarRight.setTarget(3.5);
                    break;

                case 'calm':
                default:
                    this.springHeadAngle.setTarget(0.0);
                    this.springHeadX.setTarget(0.0);
                    this.springEyeSquint.setTarget(0.0);
                    this.springBrowLeft.setTarget(0.0);
                    this.springBrowRight.setTarget(0.0);
                    this.springBrowTilt.setTarget(0.0);
                    this.springMouthWidth.setTarget(1.0);
                    this.springEarLeft.setTarget(0.0);
                    this.springEarRight.setTarget(0.0);
                    break;
            }
        }

        /**
         * Set speaking state.
         * @param {boolean} speaking
         * @param {number} [intensity=0.8]
         */
        setSpeaking(speaking, intensity = 0.8) {
            this.isSpeaking = Boolean(speaking);
            if (this.wrapper) {
                this.wrapper.classList.toggle('is-speaking', this.isSpeaking);
            }

            if (this.options.mode === 'video' && this.elVideo) {
                if (this.isSpeaking) {
                    if (this.elVideo.currentTime < 2.0 || this.elVideo.currentTime >= 9.5) {
                        this.elVideo.currentTime = 2.083;
                    }
                    this.elVideo.playbackRate = 1.0;
                    this.elVideo.play().catch(e => console.warn('[SnifferAvatar] Video play error:', e));
                } else {
                    this.elVideo.pause();
                    this.elVideo.currentTime = 2.083;
                    this.setEmotion(this.currentEmotion);
                }
                return;
            }

            if (this.isSpeaking) {
                // If not driven by external audio analyser, simulate organic speech rhythm
                if (!this.speechInterval) {
                    this.speechInterval = setInterval(() => {
                        if (!this.isSpeaking) return;
                        const pulse = Math.random();
                        const open = (pulse > 0.15 ? pulse : 0.2) * intensity;
                        const width = 0.95 + Math.random() * 0.18;
                        this.pulseSpeech(open, null, width);

                        // Organic head nod on speech rhythm
                        this.springHeadY.setTarget(Math.sin(Date.now() * 0.008) * (open * 6.0));
                    }, 110);
                }
            } else {
                if (this.speechInterval) {
                    clearInterval(this.speechInterval);
                    this.speechInterval = null;
                }
                this.springMouthOpen.setTarget(0.0);
                this.springMouthWidth.setTarget(1.0);
                this.springHeadY.setTarget(0.0);

                // Return to current emotion resting posture
                this.setEmotion(this.currentEmotion);
            }
        }

        /**
         * Real-time lip-sync pulse from TTS audio analysis or word boundary.
         * @param {number} open - Mouth opening 0.0 to 1.0.
         * @param {number} [browLift=null] - Eyebrow lift 0.0 to 1.0.
         * @param {number} [width=1.0] - Dynamic phoneme mouth width 0.85 to 1.20.
         */
        pulseSpeech(open, browLift = null, width = 1.0) {
            const clampedOpen = Math.max(0, Math.min(1, open));

            // 1. Audio-Coupled Video Lip-Sync Pacing
            if (this.options.mode === 'video' && this.elVideo) {
                if (!this.isSpeaking) return;

                const curTime = this.elVideo.currentTime || 0;
                // Loop within active speech range (2.083s Frame 50 to 9.5s)
                if (curTime >= 9.5 || curTime < 2.0) {
                    this.elVideo.currentTime = 2.083;
                }

                const frameIdx = Math.floor(curTime * 24) % 240;
                const aperture = (typeof FRAME_APERTURES !== 'undefined' && FRAME_APERTURES[frameIdx] !== undefined)
                    ? FRAME_APERTURES[frameIdx]
                    : 0.5;

                if (clampedOpen >= 0.10) {
                    // Active voice sound: ensure video is playing and modulate speed to speech energy
                    if (this.elVideo.paused) {
                        this.elVideo.play().catch(() => {});
                    }
                    // Speech speed scales dynamically: 0.85x for soft consonants up to 1.55x for loud vowels
                    const targetSpeed = 0.85 + (clampedOpen * 0.70);
                    this.elVideo.playbackRate = targetSpeed;
                } else {
                    // Silence or pause in speech (comma, period, breath, word gap)
                    if (aperture <= 0.22) {
                        // Mouth is closed: freeze on this frame!
                        this.elVideo.playbackRate = 0;
                    } else {
                        // Mouth is still open: advance briskly to the nearest closed frame (~60-80ms)
                        this.elVideo.playbackRate = 1.35;
                    }
                }
                return;
            }

            // 2. 2.5D Spring-Damper Rig Kinematics
            this.springMouthOpen.setTarget(clampedOpen);
            this.springMouthWidth.setTarget(Math.max(0.85, Math.min(1.2, width)));

            if (browLift !== null) {
                const lift = Math.max(0, Math.min(1, browLift));
                if (this.currentEmotion === 'curious') {
                    // Maintain inquisitive asymmetry during speech
                    this.springBrowLeft.setTarget(Math.min(1.0, lift * 1.15));
                    this.springBrowRight.setTarget(lift * 0.5);
                } else {
                    this.springBrowLeft.setTarget(lift);
                    this.springBrowRight.setTarget(lift);
                }
            }

            // Head nodding with speech volume
            if (this.isSpeaking) {
                const nod = Math.sin(Date.now() * 0.010) * (clampedOpen * 5.0);
                this.springHeadY.setTarget(nod);
            }
        }

        /**
         * Trigger natural eyelid blink over the exact eye positions.
         */
        blink() {
            if (!this.elEyelidLeft || !this.elEyelidRight) return;

            this.elEyelidLeft.style.opacity = '1';
            this.elEyelidLeft.style.transform = 'scaleY(1.8)';
            this.elEyelidRight.style.opacity = '1';
            this.elEyelidRight.style.transform = 'scaleY(1.8)';

            setTimeout(() => {
                if (this.elEyelidLeft && this.elEyelidRight) {
                    this.elEyelidLeft.style.opacity = '0';
                    this.elEyelidLeft.style.transform = 'scaleY(0)';
                    this.elEyelidRight.style.opacity = '0';
                    this.elEyelidRight.style.transform = 'scaleY(0)';
                }
            }, 140);
        }

        startBlinkLoop() {
            const scheduleNextBlink = () => {
                // Randomized interval with occasional double blinks
                const delay = 3500 + Math.random() * 3200;
                this.blinkTimer = setTimeout(() => {
                    this.blink();
                    if (Math.random() > 0.75) {
                        setTimeout(() => this.blink(), 240);
                    }
                    scheduleNextBlink();
                }, delay);
            };
            scheduleNextBlink();
        }

        /**
         * Sniffing animation (nose twitch) during thinking or curious states.
         */
        sniff() {
            if (!this.elMuzzle) return;
            this.elMuzzle.classList.add('snf-sniff-anim');
            setTimeout(() => {
                if (this.elMuzzle) {
                    this.elMuzzle.classList.remove('snf-sniff-anim');
                }
            }, 600);
        }

        setThinking(thinking) {
            this.isThinking = Boolean(thinking);
            if (this.wrapper) {
                this.wrapper.classList.toggle('is-thinking', this.isThinking);
            }
            if (this.isThinking) {
                this.setEmotion('curious');
            } else {
                this.setEmotion('calm');
            }
        }

        onHover(isHovering) {
            if (this.isSpeaking) return;
            if (isHovering) {
                this.springHeadAngle.setTarget(-3.0); // Inquisitive head tilt on hover
                this.springBrowLeft.setTarget(0.55);
                this.springBrowRight.setTarget(0.35);
                this.springMouthOpen.setTarget(0.12);
                this.springEyeSquint.setTarget(0.3);
            } else {
                this.setEmotion(this.currentEmotion);
            }
        }

        onClick() {
            if (this.options.mode === 'video' && this.elVideo) {
                this.elVideo.currentTime = 2.083;
                this.elVideo.playbackRate = 1.0;
                this.elVideo.play().catch(() => {});
                setTimeout(() => {
                    if (!this.isSpeaking && this.elVideo) {
                        this.elVideo.pause();
                        this.elVideo.currentTime = 2.083;
                        this.setEmotion(this.currentEmotion);
                    }
                }, 1400);
                this.wrapper.dispatchEvent(new CustomEvent('sniffer-click', { bubbles: true }));
                return;
            }

            this.blink();
            this.sniff();
            this.setEmotion('happy');
            setTimeout(() => {
                if (!this.isSpeaking) {
                    this.setEmotion('calm');
                }
            }, 1200);

            this.wrapper.dispatchEvent(new CustomEvent('sniffer-click', { bubbles: true }));
        }

        destroy() {
            if (this.blinkTimer) clearTimeout(this.blinkTimer);
            if (this.speechInterval) clearInterval(this.speechInterval);
            if (this.animFrame) cancelAnimationFrame(this.animFrame);
            if (this.wrapper && this.wrapper.parentElement) {
                this.wrapper.parentElement.removeChild(this.wrapper);
            }
        }
    }

    // Expose globally
    window.SnifferAvatar = SnifferAvatar;

})(window);
