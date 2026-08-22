<script setup lang="ts">
import { computed, ref } from 'vue';
import { t } from '../i18n';
import { useTemplateTimer } from '../state/templateTimer';
import type { PomodoroConfig } from '../types';

const store = useTemplateTimer();
const durations = [15, 25, 45];
const expanded = ref({
  options: true,
});
const customOpen = ref(!durations.includes(store.state.config.focusMin));

const config = computed(() => store.state.config);
const syncDisabled = computed(() => store.busy.value || !store.canSend.value);
const syncLabel = computed(() => (store.state.status === 'syncing' ? t('action.syncing') : t('action.show')));
const focusLabel = computed(() => String(config.value.focusMin) + ' ' + t('unit.min'));
const restLabel = computed(() => {
  return t('summary.restFormat', { short: config.value.shortBreakMin, long: config.value.longBreakMin });
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

function setSoundEnabled(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  update({ soundEnabled: checked });
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
        <span>{{ t('summary.breaks') }}</span>
        <strong>{{ restLabel }}</strong>
      </div>
      <div>
        <span>{{ t('summary.cycles') }}</span>
        <strong>{{ config.cycleCount }}</strong>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <span class="panel-icon">T</span>
        <h2>{{ t('settings.focusDuration') }}</h2>
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
          {{ t('settings.custom') }}
        </button>
      </div>
      <div v-if="customOpen" class="custom-row">
        <label for="focus-min">{{ t('settings.minutes') }}</label>
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
        <span>{{ t('settings.options') }}</span>
        <b>{{ expanded.options ? '-' : '+' }}</b>
      </button>
      <div v-if="expanded.options" class="accordion-body">
        <label class="setting-row">
          <span>{{ t('settings.autoStartNext') }}</span>
          <input
            type="checkbox"
            :checked="config.autoStartNext"
            @change="update({ autoStartNext: ($event.target as HTMLInputElement).checked })"
          />
        </label>
        <label class="setting-row">
          <span>{{ t('settings.cyclesCount') }}</span>
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
          <span>{{ t('settings.shortBreak') }}</span>
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
          <span>{{ t('settings.longBreak') }}</span>
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
      <label class="accordion-head sound-toggle-row">
        <span>{{ t('settings.soundAlerts') }}</span>
        <input
          type="checkbox"
          :checked="config.soundEnabled"
          @change="setSoundEnabled"
        />
      </label>
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
