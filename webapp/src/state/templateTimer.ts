import { computed, reactive, watch } from 'vue';
import { hasJeeWebBridge, loadPixelMug } from '../template/bubbleClient';
import { openMpsApp } from '../template/mpsLaunch';
import { useBleSession } from '../template/bleSession';
import { t } from '../i18n';
import type { AppStatus, DeviceInfo, PomodoroConfig, PomodoroRuntimeState } from '../types';

type LaunchPhase = 'idle' | 'requesting' | 'preparing' | 'switching' | 'ready' | 'failed';

const STORAGE_KEY = 'pomodoro_config_v1';
const DEFAULT_CONFIG: PomodoroConfig = {
  focusMin: 25,
  autoStartNext: false,
  cycleCount: 4,
  shortBreakMin: 5,
  longBreakMin: 15,
  soundEnabled: true,
  endSound: 'classic',
};

const state = reactive({
  status: 'idle' as AppStatus,
  message: '',
  device: null as DeviceInfo | null,
  bleState: 'idle',
  launchPhase: 'idle' as LaunchPhase,
  businessStatus: 'idle' as AppStatus,
  businessMessage: '',
  config: loadConfig(),
  runtime: null as PomodoroRuntimeState | null,
  lastSyncedAt: 0,
});

let bleSession: ReturnType<typeof useBleSession> | null = null;
let requestSeq = 0;

function getBle() {
  if (!bleSession) {
    bleSession = useBleSession();
  }
  return bleSession;
}

const busy = computed(() => ['loading', 'installing', 'connecting', 'syncing'].includes(state.status));
const canSend = computed(() => Boolean(state.device) && getBle().isReady.value);
const statusText = computed(() => {
  if (!state.message) return '';
  return hasJeeWebBridge() ? state.message : `${state.message} ${t('status.browserMock')}`;
});
const businessStatusText = computed(() => state.businessMessage);
const canEnter = computed(() => state.launchPhase === 'ready');
const openButtonLabel = computed(() => {
  if (busy.value) return t('landing.opening');
  if (state.launchPhase === 'ready') return t('landing.enter');
  if (state.launchPhase === 'failed') return t('landing.retry');
  return t('landing.install');
});

watch(
  () => state.config,
  (config) => saveConfig(config),
  { deep: true },
);

export function useTemplateTimer() {
  async function refreshDevice() {
    state.status = 'loading';
    state.message = t('status.loadingDevice');
    try {
      const result = await loadPixelMug();
      state.device = result;
      state.status = result ? 'ready' : 'error';
      state.message = result ? t('status.deviceReady') : t('status.deviceMissing');
    } catch (error) {
      state.status = 'error';
      state.message = errorMessage(error);
    }
  }

  async function openOnDevice() {
    if (!state.device) {
      await refreshDevice();
    }

    const target = state.device || (await loadPixelMug());
    if (!target) {
      state.status = 'error';
      state.message = t('status.deviceMissing');
      return false;
    }

    state.device = target;
    state.status = 'installing';
    state.launchPhase = 'requesting';
    state.message = t('status.opening');
    try {
      await openMpsApp(target, undefined, {
        onPhase: updateLaunchPhase,
      });
      markLaunchReady();
      return true;
    } catch (error) {
      state.status = 'error';
      state.launchPhase = 'failed';
      state.message = errorMessage(error);
      return false;
    }
  }

  async function connectDevice() {
    const target = state.device || (await loadPixelMug());
    if (!target) {
      state.status = 'error';
      state.message = t('status.deviceMissing');
      return;
    }

    state.device = target;
    state.status = 'connecting';
    state.message = t('status.connectingBle');
    const ble = getBle();
    try {
      await ble.ensureConnected(target);
      state.bleState = ble.state.connection;
      state.status = 'connected';
      state.message = t('status.bleConnected');
      await sendHello();
    } catch (error) {
      state.status = 'error';
      state.message = errorMessage(error);
    }
  }

  async function syncConfig() {
    const target = state.device || (await loadPixelMug());
    if (!target) {
      state.status = 'error';
      state.businessStatus = 'error';
      state.businessMessage = t('status.deviceMissing');
      return false;
    }

    state.device = target;
    state.status = 'syncing';
    state.businessStatus = 'syncing';
    state.businessMessage = t('status.syncingSettings');

    try {
      const response = await getBle().send(target, {
        v: 1,
        id: nextRequestId('sync'),
        type: 'cmd',
        cmd: 'sync_config',
        payload: {
          config: toWireConfig(state.config),
          applyMode: 'ready',
        },
      });
      const ok = ackOk(response);
      if (!ok) throw new Error(t('status.syncFailed'));
      state.status = 'connected';
      state.businessStatus = 'connected';
      state.businessMessage = t('status.syncSuccess');
      state.lastSyncedAt = Date.now();
      return true;
    } catch (error) {
      state.status = 'error';
      state.businessStatus = 'error';
      state.businessMessage = errorMessage(error);
      return false;
    }
  }

  async function sendHello() {
    if (!state.device) return;
    try {
      const response = await getBle().send(state.device, {
        v: 1,
        id: nextRequestId('hello'),
        type: 'cmd',
        cmd: 'hello',
        payload: {
          app: 'pomodoro',
          client: 'webapp',
        },
      });
      const payload = ackPayload(response);
      const runtime = payload?.state as PomodoroRuntimeState | undefined;
      if (runtime) state.runtime = runtime;
    } catch {
      // BLE is connected; hello is only a best-effort state refresh.
    }
  }

  function updateConfig(patch: Partial<PomodoroConfig>) {
    Object.assign(state.config, normalizeConfig({ ...state.config, ...patch }));
  }

  function bindBleState() {
    refreshDevice();
    return getBle().bindState();
  }

  return {
    state,
    busy,
    canSend,
    canEnter,
    openButtonLabel,
    statusText,
    businessStatusText,
    bindBleState,
    connectDevice,
    openOnDevice,
    refreshDevice,
    sendHello,
    syncConfig,
    updateConfig,
  };
}

function markLaunchReady() {
  state.status = 'ready';
  state.launchPhase = 'ready';
  state.message = t('status.launchReady');
}

function updateLaunchPhase(phase: LaunchPhase) {
  state.launchPhase = phase;
  if (phase === 'requesting') {
    state.message = t('status.opening');
  } else if (phase === 'preparing') {
    state.message = t('status.preparing');
  } else if (phase === 'switching') {
    state.message = t('status.switching');
  } else if (phase === 'ready') {
    state.message = t('status.launchReady');
  }
}

function loadConfig(): PomodoroConfig {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_CONFIG };
    return normalizeConfig({ ...DEFAULT_CONFIG, ...JSON.parse(raw) });
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

function saveConfig(config: PomodoroConfig) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(toWireConfig(config)));
}

function normalizeConfig(config: PomodoroConfig): PomodoroConfig {
  return {
    focusMin: clampInt(config.focusMin, 1, 60, DEFAULT_CONFIG.focusMin),
    autoStartNext: Boolean(config.autoStartNext),
    cycleCount: clampInt(config.cycleCount, 1, 12, DEFAULT_CONFIG.cycleCount),
    shortBreakMin: clampInt(config.shortBreakMin, 1, 60, DEFAULT_CONFIG.shortBreakMin),
    longBreakMin: clampInt(config.longBreakMin, 1, 60, DEFAULT_CONFIG.longBreakMin),
    soundEnabled: Boolean(config.soundEnabled),
    endSound: config.endSound === 'gentle' ? 'gentle' : 'classic',
  };
}

function toWireConfig(config: PomodoroConfig): PomodoroConfig {
  return normalizeConfig(config);
}

function clampInt(value: unknown, min: number, max: number, fallback: number) {
  const next = Number.parseInt(String(value), 10);
  if (!Number.isFinite(next)) return fallback;
  return Math.min(max, Math.max(min, next));
}

function nextRequestId(prefix: string) {
  requestSeq += 1;
  return `${prefix}_${Date.now()}_${requestSeq}`;
}

function ackOk(response: unknown) {
  if (!hasJeeWebBridge()) return true;
  const data = response as { result?: unknown; ok?: unknown; code?: unknown };
  const result = data?.result as { ok?: unknown } | undefined;
  return result?.ok === true || data?.ok === true || data?.code === 200;
}

function ackPayload(response: unknown) {
  const data = response as { result?: unknown; payload?: unknown };
  const result = data?.result as { payload?: unknown } | undefined;
  return (result?.payload || data?.payload || {}) as Record<string, unknown>;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error || t('status.unknownError'));
}