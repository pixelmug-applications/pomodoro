import { computed, reactive } from 'vue';
import { BleAppClient } from '../../../../jeejio-bubble/sdk/BleAppClient.js';
import type { DeviceInfo, PomodoroRuntimeState } from '../types';
import { getWebApp, hasJeeWebBridge } from './bubbleClient';

type LegacyBlePayload = {
  [key: string]: unknown;
  cmd?: string;
  method?: string;
  payload?: Record<string, unknown>;
  params?: Record<string, unknown>;
};

type WireConfig = {
  f?: number;
  a?: boolean;
  c?: number;
  s?: number;
  l?: number;
  e?: boolean;
};

type WireState = {
  s?: string;
  p?: string;
  z?: boolean;
  d?: number;
  l?: number;
  g?: number;
  c?: number;
  n?: 'short' | 'long' | null;
  f?: WireConfig;
};

const APP_ID = 'Pomodoro';
const READY_STATE = 'ready';
const UNAVAILABLE_STATES = new Set(['disconnected', 'failed']);

const state = reactive({
  connection: 'idle',
  message: '',
  lastError: '',
});

let currentDevice: DeviceInfo | null = null;
let client: BleAppClient | null = null;

const isReady = computed(() => state.connection === READY_STATE || !hasJeeWebBridge());
const isConnecting = computed(() => state.connection === 'connecting');
const isUnavailable = computed(() => UNAVAILABLE_STATES.has(state.connection));

export function useBleSession() {
  async function ensureConnected(device: DeviceInfo) {
    currentDevice = device;
    if (!hasJeeWebBridge()) {
      state.connection = READY_STATE;
      state.message = 'BLE mock connected.';
      return;
    }
    await getClient().ensureConnected(device);
  }

  async function reconnect() {
    if (!currentDevice || !hasJeeWebBridge()) return;
    await getClient().reconnect();
  }

  async function send(
    device: DeviceInfo,
    payload: LegacyBlePayload,
    options: Record<string, unknown> = {},
  ) {
    await ensureConnected(device);
    if (!hasJeeWebBridge()) {
      return { code: 200, ok: true, result: { ok: true, payload: {} }, mock: true };
    }

    const method = String(payload.cmd || payload.method || '');
    if (!method) throw new Error('BLE command method is required');
    const params = payload.payload || payload.params || {};
    const response = await getClient().command(method, params, options);
    return toLegacyResponse(response);
  }

  function bindState() {
    // BleAppClient owns the bridge listener for the lifetime of the WebApp.
    if (hasJeeWebBridge()) getClient();
    return () => undefined;
  }

  return {
    state,
    isReady,
    isConnecting,
    isUnavailable,
    bindState,
    ensureConnected,
    reconnect,
    send,
  };
}

function getClient() {
  if (client) return client;
  client = new BleAppClient(getWebApp().ble!, {
    appId: APP_ID,
    appVersion: '1.0.0',
    connectTimeoutMillis: 15000,
    sendTimeoutMillis: 5000,
  });
  client.on('connectionState', (event) => {
    state.connection = String(event.connection || 'unknown');
    state.message = event.message || '';
    state.lastError = event.lastError || '';
  });
  return client;
}

function toLegacyResponse(response: unknown) {
  const message = response as { result?: unknown; rev?: number };
  const result = decodeResult(message?.result);
  return {
    code: 200,
    ok: true,
    result: {
      ok: true,
      payload: result,
      rev: message?.rev,
    },
  };
}

function decodeResult(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object') return {};
  const result = { ...(value as Record<string, unknown>) };
  if (isWireState(result.state)) result.state = decodeWireState(result.state);
  return result;
}

function isWireState(value: unknown): value is WireState {
  return Boolean(value && typeof value === 'object' && ('s' in value || 'd' in value));
}

function decodeWireState(wire: WireState): PomodoroRuntimeState {
  const runtime: PomodoroRuntimeState = {
    state: String(wire.s || ''),
    phase: String(wire.p || ''),
    paused: Boolean(wire.z),
    durationSec: Number(wire.d || 0),
    timeLeftSec: Number(wire.l || 0),
    progress: Number(wire.g || 0),
  };
  if (wire.c != null) runtime.completedCycles = Number(wire.c);
  if (wire.n !== undefined) runtime.nextRestType = wire.n;
  if (wire.f) {
    runtime.config = {
      focusMin: Number(wire.f.f || 0),
      autoStartNext: Boolean(wire.f.a),
      cycleCount: Number(wire.f.c || 0),
      shortBreakMin: Number(wire.f.s || 0),
      longBreakMin: Number(wire.f.l || 0),
      soundEnabled: Boolean(wire.f.e),
    };
  }
  return runtime;
}
