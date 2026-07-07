<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { LOADING_IMAGE } from '../assets';
import { t } from '../i18n';
import { useTemplateTimer } from '../state/templateTimer';

type LandingStep = 'open' | 'enter';

const router = useRouter();
const store = useTemplateTimer();
const step = ref<LandingStep>('open');

async function handleOpen() {
  const ok = await store.openOnDevice();
  step.value = ok ? 'enter' : 'open';
}

async function handleEnter() {
  if (!store.canEnter.value) {
    await handleOpen();
    return;
  }
  router.push('/timers');
  await store.connectDevice();
}

</script>

<template>
  <main class="landing" :class="step">
    <div class="landing-visual" aria-hidden="true">
      <div class="loading-device">
        <img :src="LOADING_IMAGE" alt="" />
      </div>
    </div>

    <div class="landing-copy">
      <h1>{{ t('app.title') }}</h1>
      <p>{{ t('landing.subtitle') }}</p>
    </div>

    <div class="landing-actions">
      <button class="landing-primary" :disabled="store.busy.value" @click="step === 'enter' ? handleEnter() : handleOpen()">
        {{ store.openButtonLabel.value }}
      </button>
      <p
        v-if="store.statusText.value"
        :class="store.state.status === 'error' ? 'landing-error' : 'landing-status'"
      >
        {{ store.statusText.value }}
      </p>
    </div>
  </main>
</template>
