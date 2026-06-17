<script setup lang="ts">
import { computed, ref } from 'vue';
import { SOUND_PREVIEWS } from '../assets';
import { useTemplateTimer } from '../state/templateTimer';
import type { EndSound, PomodoroConfig, ScreenTheme } from '../types';

const store = useTemplateTimer();
const durations = [15, 25, 45];
const expanded = ref({
  options: true,
  sound: true,
  screen: true,
});
const customOpen = ref(!durations.includes(store.state.config.focusMin));
let previewAudio: HTMLAudioElement | null = null;
const activePreview = ref<EndSound | null>(null);

const config = computed(() => store.state.config);
const syncDisabled = computed(() => store.busy.value || !store.canSend.value);
const syncLabel = computed(() => (store.state.status === 'syncing' ? 'Syncing...' : 'Show'));
const focusLabel = computed(() => `${config.value.focusMin} min`);
const restLabel = computed(() => {
  return `${config.value.shortBreakMin}m short / ${config.value.longBreakMin}m long`;
});

function selectDuration(value: number) {
  customOpen.value = false;
  update({ focusMin: value });
}

function setCustomFocus(event: Event) {
  customOpen.value = true;
  const value = (event.target as HTMLInputElement).value;
  update({ focusMin: toInt(value, 1, 60, config.value.focusMin) });
}

function updateNumber(key: keyof Pick<PomodoroConfig, 'cycleCount' | 'shortBreakMin' | 'longBreakMin'>, event: Event) {
  const value = (event.target as HTMLInputElement).value;
  const max = key === 'cycleCount' ? 12 : 60;
  update({ [key]: toInt(value, 1, max, config.value[key]) } as Partial<PomodoroConfig>);
}

function update(patch: Partial<PomodoroConfig>) {
  store.updateConfig(patch);
}

function toggle(section: keyof typeof expanded.value) {
  expanded.value[section] = !expanded.value[section];
}

async function syncConfig() {
  await store.syncConfig();
}

function stopPreview() {
  if (previewAudio) {
    previewAudio.pause();
    previewAudio.currentTime = 0;
  }
  previewAudio = null;
  activePreview.value = null;
}

function chooseSound(sound: EndSound) {
  update({ endSound: sound });
  if (!config.value.soundEnabled) {
    stopPreview();
    return;
  }
  if (activePreview.value === sound && previewAudio && !previewAudio.paused) {
    stopPreview();
    return;
  }
  stopPreview();
  previewAudio = new Audio(SOUND_PREVIEWS[sound]);
  previewAudio.volume = 0.8;
  previewAudio.onended = () => {
    activePreview.value = null;
    previewAudio = null;
  };
  activePreview.value = sound;
  previewAudio.play().catch(() => {
    stopPreview();
  });
}

function setSoundEnabled(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  update({ soundEnabled: checked });
  if (!checked) {
    stopPreview();
  }
}

function toInt(value: string, min: number, max: number, fallback: number) {
  const next = Number.parseInt(value, 10);
  if (!Number.isFinite(next)) return fallback;
  return Math.min(max, Math.max(min, next));
}
</script>

<template>
  <main class="pomodoro-page">
    <section class="pomodoro-header">
      <div>
        <p class="eyebrow">PixelMug Pomodoro</p>
        <h1>{{ focusLabel }}</h1>
      </div>
    </section>

    <section class="summary-strip">
      <div>
        <span>Breaks</span>
        <strong>{{ restLabel }}</strong>
      </div>
      <div>
        <span>Cycles</span>
        <strong>{{ config.cycleCount }}</strong>
      </div>
      <div>
        <span>Theme</span>
        <strong>{{ config.theme === 'pulse' ? 'Pulse' : 'Retro' }}</strong>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span class="panel-icon">T</span>
        <h2>Focus Duration</h2>
      </div>
      <div class="duration-grid">
        <button
          v-for="duration in durations"
          :key="duration"
          type="button"
          :class="{ selected: !customOpen && config.focusMin === duration }"
          @click="selectDuration(duration)"
        >
          {{ duration }}m
        </button>
        <button type="button" :class="{ selected: customOpen }" @click="customOpen = true">
          Custom
        </button>
      </div>
      <div v-if="customOpen" class="custom-row">
        <label for="focus-min">Minutes</label>
        <input
          id="focus-min"
          type="number"
          min="1"
          max="60"
          :value="config.focusMin"
          @input="setCustomFocus"
          @blur="setCustomFocus"
        />
      </div>
    </section>

    <section class="accordion">
      <button type="button" class="accordion-head" @click="toggle('options')">
        <span>Pomodoro Options</span>
        <b>{{ expanded.options ? '-' : '+' }}</b>
      </button>
      <div v-if="expanded.options" class="accordion-body">
        <label class="setting-row">
          <span>Auto-start next tomato</span>
          <input
            type="checkbox"
            :checked="config.autoStartNext"
            @change="update({ autoStartNext: ($event.target as HTMLInputElement).checked })"
          />
        </label>
        <label class="setting-row">
          <span>Cycles count</span>
          <input
            type="number"
            min="1"
            max="12"
            :value="config.cycleCount"
            @input="updateNumber('cycleCount', $event)"
            @blur="updateNumber('cycleCount', $event)"
          />
        </label>
        <label class="setting-row">
          <span>Short Break (min)</span>
          <input
            type="number"
            min="1"
            max="60"
            :value="config.shortBreakMin"
            @input="updateNumber('shortBreakMin', $event)"
            @blur="updateNumber('shortBreakMin', $event)"
          />
        </label>
        <label class="setting-row">
          <span>Long Break (min)</span>
          <input
            type="number"
            min="1"
            max="60"
            :value="config.longBreakMin"
            @input="updateNumber('longBreakMin', $event)"
            @blur="updateNumber('longBreakMin', $event)"
          />
        </label>
      </div>
    </section>

    <section class="accordion">
      <button type="button" class="accordion-head" @click="toggle('sound')">
        <span>Sound & Alerts</span>
        <b>{{ expanded.sound ? '-' : '+' }}</b>
      </button>
      <div v-if="expanded.sound" class="accordion-body">
        <label class="setting-row">
          <span>Sound Master Switch</span>
          <input
            type="checkbox"
            :checked="config.soundEnabled"
            @change="setSoundEnabled"
          />
        </label>
        <div class="segmented">
          <button
            type="button"
            :class="{ selected: config.endSound === 'classic', playing: activePreview === 'classic' }"
            @click="chooseSound('classic')"
          >
            Classic
          </button>
          <button
            type="button"
            :class="{ selected: config.endSound === 'gentle', playing: activePreview === 'gentle' }"
            @click="chooseSound('gentle')"
          >
            Gentle
          </button>
        </div>
      </div>
    </section>

    <section class="accordion">
      <button type="button" class="accordion-head" @click="toggle('screen')">
        <span>Screen Display</span>
        <b>{{ expanded.screen ? '-' : '+' }}</b>
      </button>
      <div v-if="expanded.screen" class="accordion-body">
        <div class="segmented">
          <button
            type="button"
            :class="{ selected: config.theme === 'pulse' }"
            @click="update({ theme: 'pulse' as ScreenTheme })"
          >
            Pulse
          </button>
          <button
            type="button"
            :class="{ selected: config.theme === 'retro' }"
            @click="update({ theme: 'retro' as ScreenTheme })"
          >
            Retro
          </button>
        </div>
      </div>
    </section>

    <p v-if="store.businessStatusText.value" class="sync-note" :class="{ error: store.state.businessStatus === 'error' }">
      {{ store.businessStatusText.value }}
    </p>

    <div class="sync-bar">
      <button type="button" :disabled="syncDisabled" @click="syncConfig">
        {{ syncLabel }}
      </button>
    </div>
  </main>
</template>
