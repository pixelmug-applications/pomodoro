<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { hasJeeWebBridge } from '../bubbleClient';
import { useBleSession } from '../bleSession';

const CONNECT_COUNTDOWN_SECONDS = 15;

const ble = useBleSession();
const connectingSeconds = ref(CONNECT_COUNTDOWN_SECONDS);
let countdownTimer: number | undefined;

const hasBridge = computed(() => hasJeeWebBridge());
const visible = computed(() => {
  if (!hasBridge.value) return false;
  return !ble.isReady.value;
});

const tone = computed(() => {
  if (ble.isConnecting.value) return 'busy';
  return 'offline';
});

const label = computed(() => {
  if (ble.isConnecting.value) return `Connecting BLE (${connectingSeconds.value}s)`;
  if (ble.state.message === 'Connecting BLE...' || ble.state.message === 'Connecting BLE') {
    return 'BLE disconnected';
  }
  if (ble.state.message) return ble.state.message;
  return 'BLE disconnected';
});

const canRetry = computed(() => hasBridge.value && !ble.isReady.value && !ble.isConnecting.value);

watch(
  () => ble.isConnecting.value,
  (connecting) => {
    window.clearInterval(countdownTimer);
    if (!connecting) {
      connectingSeconds.value = CONNECT_COUNTDOWN_SECONDS;
      return;
    }
    connectingSeconds.value = CONNECT_COUNTDOWN_SECONDS;
    countdownTimer = window.setInterval(() => {
      connectingSeconds.value = Math.max(0, connectingSeconds.value - 1);
    }, 1000);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  window.clearInterval(countdownTimer);
});

async function retry() {
  await ble.reconnect();
}
</script>

<template>
  <div v-if="visible" class="ble-status-banner-wrap">
    <div class="ble-status-banner" :class="tone">
      <span class="ble-status-dot" />
      <span class="ble-status-text">{{ label }}</span>
      <button v-if="canRetry" type="button" @click="retry">Retry</button>
    </div>
  </div>
</template>
