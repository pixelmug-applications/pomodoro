import type { DeviceInfo } from '../types';

import { BubbleWebApp } from '../../../../jeejio-bubble/sdk/WebApp.js';

export type DeviceEventItem = {
  method?: string;
  name?: string;
  params?: {
    value?: unknown;
  };
};

export type DeviceEventPayload = {
  payload?: {
    device?: DeviceInfo;
    events?: DeviceEventItem[];
  };
};

const TARGET_DEVICE_TAL_ID = 'PixelMugS1';

type DeviceLookupWebApp = BubbleWebApp & {
  getDevice?: (options?: Record<string, unknown>) => Promise<unknown>;
};

let webapp: BubbleWebApp | null = null;

export function hasJeeWebBridge() {
  return Boolean((globalThis as { JeeWeb?: unknown }).JeeWeb);
}

export function getWebApp() {
  if (!webapp) {
    webapp = new BubbleWebApp({
      debug: import.meta.env.DEV,
      timeoutMillis: 20000,
    });
  }

  return webapp;
}

export async function loadPixelMug() {
  if (!hasJeeWebBridge()) {
    return {
      name: 'PixelMugS1 Mock',
      talId: TARGET_DEVICE_TAL_ID,
      slotId: 'mock-slot',
      online: true,
    } satisfies DeviceInfo;
  }

  const app = getWebApp() as DeviceLookupWebApp;
  if (typeof app.getDevice === 'function') {
    const device = normalizeDevice(await app.getDevice({ talId: TARGET_DEVICE_TAL_ID }));
    if (device && matchesTargetDevice(device)) return device;
  }

  const devices = (await getWebApp().getDevices()) as DeviceInfo[];
  const device = devices[0] || null;
  return device && matchesTargetDevice(device) ? device : null;
}

export async function subscribePixelMugEvents(device: DeviceInfo) {
  if (!hasJeeWebBridge()) return;
  await getWebApp().subscribeDeviceEvents(device);
}

export function onPixelMugEvent(handler: (event: DeviceEventPayload) => void) {
  if (!hasJeeWebBridge()) return () => undefined;
  getWebApp().onDeviceEvent((event: unknown) => handler(event as DeviceEventPayload));
  return () => undefined;
}

function normalizeDevice(value: unknown) {
  if (!value || typeof value !== 'object') return null;
  const payload = value as { result?: unknown; device?: unknown };
  return (payload.result || payload.device || value) as DeviceInfo;
}

function matchesTargetDevice(device: DeviceInfo) {
  const candidate = device as DeviceInfo & { deviceTalId?: string };
  return normalizeId(candidate.talId || candidate.deviceTalId) === TARGET_DEVICE_TAL_ID;
}

function normalizeId(value: unknown) {
  return String(value || '').trim();
}
